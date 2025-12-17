using Mockups.Repositories.Carts;
using Mockups.Repositories.MenuItems;
using Mockups.Services.Carts;
using Mockups.Storage;
using Mockups.Tests.TestSupport;

namespace Mockups.Tests;

public class CartsServiceTests
{
    [Fact]
    public async Task AddItemToCart_Throws_WhenMenuItemNotFound()
    {
        var (conn, db) = SqliteTestDb.Create();
        await using var _ = db;
        await using var __ = conn;

        var menuRepo = new MenuItemRepository(db);
        var cartsRepo = new CartsRepository();
        var svc = new CartsService(menuRepo, cartsRepo);

        await Assert.ThrowsAsync<KeyNotFoundException>(() =>
            svc.AddItemToCart(Guid.NewGuid(), Guid.NewGuid().ToString(), amount: 1));
    }

    [Fact]
    public async Task GetUsersCart_ReturnsNamesAndAmounts()
    {
        var (conn, db) = SqliteTestDb.Create();
        await using var _ = db;
        await using var __ = conn;

        var userId = Guid.NewGuid();

        var itemId = Guid.NewGuid();
        db.MenuItems.Add(new MenuItem
        {
            Id = itemId,
            Name = "Pizza",
            Description = "d",
            Price = 10,
            Category = MenuItemCategory.Pizza,
            IsVegan = false,
            PhotoPath = ""
        });
        await db.SaveChangesAsync();

        var menuRepo = new MenuItemRepository(db);
        var cartsRepo = new CartsRepository();
        var svc = new CartsService(menuRepo, cartsRepo);

        await svc.AddItemToCart(userId, itemId.ToString(), 3);

        var cart = await svc.GetUsersCart(userId);

        Assert.Single(cart.Items);
        Assert.Equal(itemId, cart.Items[0].Id);
        Assert.Equal("Pizza", cart.Items[0].Name);
        Assert.Equal(3, cart.Items[0].Amount);
    }
}