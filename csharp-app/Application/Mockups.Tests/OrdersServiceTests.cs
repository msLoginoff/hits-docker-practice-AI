using Microsoft.EntityFrameworkCore;
using Moq;
using Mockups.Configs;
using Mockups.Models.Account;
using Mockups.Models.Cart;
using Mockups.Models.Menu;
using Mockups.Models.Orders;
using Mockups.Repositories.Orders;
using Mockups.Services.Addresses;
using Mockups.Services.Carts;
using Mockups.Services.MenuItems;
using Mockups.Services.Orders;
using Mockups.Services.Users;
using Mockups.Storage;
using Mockups.Tests.TestSupport;

namespace Mockups.Tests;

public class OrdersServiceTests
{
    [Fact]
    public async Task CreateOrder_PersistsOrderAndItems_AndClearsCart()
    {
        var (conn, db) = SqliteTestDb.Create();
        await using var _ = db;
        await using var __ = conn;

        var userId = Guid.NewGuid();
        var item1 = Guid.NewGuid();
        var item2 = Guid.NewGuid();

        // FK-friendly seed
        db.MenuItems.AddRange(
            new MenuItem { Id = item1, Name = "A", Description = "d", Price = 100, Category = MenuItemCategory.Pizza, IsVegan = false, PhotoPath = "" },
            new MenuItem { Id = item2, Name = "B", Description = "d", Price = 200, Category = MenuItemCategory.Soup, IsVegan = true, PhotoPath = "" }
        );
        await db.SaveChangesAsync();

        var carts = new Mock<ICartsService>();
        carts.Setup(x => x.GetUsersCart(userId, It.IsAny<bool>()))
            .ReturnsAsync(new CartIndexViewModel
            {
                Items =
                {
                    new CartMenuItemViewModel { Id = item1, Name = "A", Amount = 2 },
                    new CartMenuItemViewModel { Id = item2, Name = "B", Amount = 1 },
                }
            });

        var users = new Mock<IUsersService>();
        users.Setup(x => x.GetUserInfo(userId))
            .ReturnsAsync(new IndexViewModel { BirthDate = new DateTime(1995, 1, 1) });

        var addresses = new Mock<IAddressesService>();

        var menu = new Mock<IMenuItemsService>();
        menu.Setup(x => x.GetItemModelById(item1.ToString()))
            .ReturnsAsync(new MenuItemViewModel { Id = item1, Price = 100 });
        menu.Setup(x => x.GetItemModelById(item2.ToString()))
            .ReturnsAsync(new MenuItemViewModel { Id = item2, Price = 200 });

        var clock = new FakeDateTimeProvider { Now = new DateTime(2025, 12, 17, 9, 0, 0) }; // не ланч
        var repo = new OrdersRepository(db);
        var cfg = new OrderConfig { MinDeliveryTime = 60, DeliveryTimeStep = 15 };

        var svc = new OrdersService(repo, carts.Object, users.Object, addresses.Object, cfg, menu.Object, clock);

        await svc.CreateOrder(new OrderCreatePostViewModel
        {
            Address = "Street 1",
            DeliveryTime = clock.Now.AddHours(2)
        }, userId);

        var order = await db.Orders.SingleAsync();
        Assert.Equal(userId, order.UserId);
        Assert.Equal("Street 1", order.Address);
        Assert.Equal(OrderStatus.New, order.Status);

        // cost = 100*2 + 200*1 = 400
        Assert.Equal(400f, order.Cost);
        Assert.Equal(0f, order.Discount);

        var items = await db.OrderMenuItems.ToListAsync();
        Assert.Equal(2, items.Count);
        Assert.Contains(items, x => x.ItemId == item1 && x.Amount == 2);
        Assert.Contains(items, x => x.ItemId == item2 && x.Amount == 1);

        carts.Verify(x => x.ClearUsersCart(userId), Times.Once);
    }

    [Fact]
    public async Task CreateOrder_AppliesLunchDiscount_WhenLunchTime()
    {
        var (conn, db) = SqliteTestDb.Create();
        await using var _ = db;
        await using var __ = conn;

        var userId = Guid.NewGuid();
        var itemId = Guid.NewGuid();

        db.MenuItems.Add(new MenuItem { Id = itemId, Name = "A", Description = "d", Price = 100, Category = MenuItemCategory.Pizza, IsVegan = false, PhotoPath = "" });
        await db.SaveChangesAsync();

        var carts = new Mock<ICartsService>();
        carts.Setup(x => x.GetUsersCart(userId, It.IsAny<bool>()))
            .ReturnsAsync(new CartIndexViewModel
            {
                Items = { new CartMenuItemViewModel { Id = itemId, Name = "A", Amount = 1 } }
            });

        var users = new Mock<IUsersService>();
        // др далеко
        users.Setup(x => x.GetUserInfo(userId))
            .ReturnsAsync(new IndexViewModel { BirthDate = new DateTime(1990, 1, 1) });

        var menu = new Mock<IMenuItemsService>();
        menu.Setup(x => x.GetItemModelById(itemId.ToString()))
            .ReturnsAsync(new MenuItemViewModel { Id = itemId, Price = 100 });

        var clock = new FakeDateTimeProvider { Now = new DateTime(2025, 12, 17, 12, 0, 0) }; // ланч
        var repo = new OrdersRepository(db);
        var cfg = new OrderConfig { MinDeliveryTime = 60, DeliveryTimeStep = 15 };

        var svc = new OrdersService(repo, carts.Object, users.Object, Mock.Of<IAddressesService>(), cfg, menu.Object, clock);

        await svc.CreateOrder(new OrderCreatePostViewModel { Address = "X", DeliveryTime = clock.Now.AddHours(1) }, userId);

        var order = await db.Orders.SingleAsync();
        Assert.Equal(10f, order.Discount);
    }

    [Fact]
    public async Task CreateOrder_BirthdayDiscount_TakesPrecedenceOverLunch()
    {
        var (conn, db) = SqliteTestDb.Create();
        await using var _ = db;
        await using var __ = conn;

        var userId = Guid.NewGuid();
        var itemId = Guid.NewGuid();

        db.MenuItems.Add(new MenuItem { Id = itemId, Name = "A", Description = "d", Price = 100, Category = MenuItemCategory.Pizza, IsVegan = false, PhotoPath = "" });
        await db.SaveChangesAsync();

        var carts = new Mock<ICartsService>();
        carts.Setup(x => x.GetUsersCart(userId, It.IsAny<bool>()))
            .ReturnsAsync(new CartIndexViewModel
            {
                Items = { new CartMenuItemViewModel { Id = itemId, Name = "A", Amount = 1 } }
            });

        var clock = new FakeDateTimeProvider { Now = new DateTime(2025, 12, 17, 12, 0, 0) }; // ланч
        var birthDate = clock.Now.AddDays(1).AddYears(-30); // др завтра (в пределах 3 дней)

        var users = new Mock<IUsersService>();
        users.Setup(x => x.GetUserInfo(userId))
            .ReturnsAsync(new IndexViewModel { BirthDate = birthDate });

        var menu = new Mock<IMenuItemsService>();
        menu.Setup(x => x.GetItemModelById(itemId.ToString()))
            .ReturnsAsync(new MenuItemViewModel { Id = itemId, Price = 100 });

        var repo = new OrdersRepository(db);
        var cfg = new OrderConfig { MinDeliveryTime = 60, DeliveryTimeStep = 15 };

        var svc = new OrdersService(repo, carts.Object, users.Object, Mock.Of<IAddressesService>(), cfg, menu.Object, clock);

        await svc.CreateOrder(new OrderCreatePostViewModel { Address = "X", DeliveryTime = clock.Now.AddHours(1) }, userId);

        var order = await db.Orders.SingleAsync();
        Assert.Equal(15f, order.Discount); // именно 15, не 10
    }
}