using Mockups.Repositories.Carts;
using Mockups.Storage;

namespace Mockups.Tests;

public class CartsRepositoryTests
{
    [Fact]
    public void GetUsersCart_CreatesCartOnce_AndReturnsSameInstance()
    {
        var repo = new CartsRepository();
        var userId = Guid.NewGuid();

        var c1 = repo.GetUsersCart(userId);
        var c2 = repo.GetUsersCart(userId);

        Assert.Same(c1, c2);
        Assert.Equal(userId, c1.UserId);
        Assert.NotNull(c1.Items);
    }

    [Fact]
    public void AddItemToCart_AddsNewItem_WhenNotExists()
    {
        var repo = new CartsRepository();
        var userId = Guid.NewGuid();
        var itemId = Guid.NewGuid();

        repo.AddItemToCart(userId, new CartMenuItem { MenuItemId = itemId, Amount = 2 });

        var cart = repo.GetUsersCart(userId);
        Assert.Single(cart.Items);
        Assert.Equal(itemId, cart.Items[0].MenuItemId);
        Assert.Equal(2, cart.Items[0].Amount);
    }

    [Fact]
    public void AddItemToCart_IncrementsAmount_WhenItemAlreadyExists()
    {
        var repo = new CartsRepository();
        var userId = Guid.NewGuid();
        var itemId = Guid.NewGuid();

        repo.AddItemToCart(userId, new CartMenuItem { MenuItemId = itemId, Amount = 2 });
        repo.AddItemToCart(userId, new CartMenuItem { MenuItemId = itemId, Amount = 3 });

        var cart = repo.GetUsersCart(userId);
        Assert.Single(cart.Items);
        Assert.Equal(5, cart.Items[0].Amount);
    }

    [Fact]
    public void DeleteItemFromCart_RemovesItem()
    {
        var repo = new CartsRepository();
        var userId = Guid.NewGuid();
        var itemId = Guid.NewGuid();

        repo.AddItemToCart(userId, new CartMenuItem { MenuItemId = itemId, Amount = 1 });
        repo.DeleteItemFromCart(userId, itemId);

        var cart = repo.GetUsersCart(userId);
        Assert.Empty(cart.Items);
    }

    [Fact]
    public void GetCartItemCount_ReturnsTotalAmount()
    {
        var repo = new CartsRepository();
        var userId = Guid.NewGuid();

        repo.AddItemToCart(userId, new CartMenuItem { MenuItemId = Guid.NewGuid(), Amount = 2 });
        repo.AddItemToCart(userId, new CartMenuItem { MenuItemId = Guid.NewGuid(), Amount = 4 });

        var count = repo.GetCartItemCount(userId);

        Assert.Equal(6, count);
    }

    [Fact]
    public void ClearUsersCart_ClearsOnlyItems()
    {
        var repo = new CartsRepository();
        var userId = Guid.NewGuid();

        repo.AddItemToCart(userId, new CartMenuItem { MenuItemId = Guid.NewGuid(), Amount = 2 });
        repo.ClearUsersCart(userId);

        var cart = repo.GetUsersCart(userId);
        Assert.Empty(cart.Items);
        Assert.Equal(userId, cart.UserId);
    }

    [Fact]
    public void GetInactiveCarts_ReturnsCartsWithLastUpdatedOlderOrEqualThreshold()
    {
        var repo = new CartsRepository();

        var activeUser = Guid.NewGuid();
        var inactiveUser = Guid.NewGuid();

        // создаём обе корзины
        var active = repo.GetUsersCart(activeUser);
        var inactive = repo.GetUsersCart(inactiveUser);

        // искусственно делаем одну "старой"
        inactive.LastUpdated = DateTime.Now.AddMinutes(-30);
        active.LastUpdated = DateTime.Now;

        var inactiveCarts = repo.GetInactiveCarts(inactiveTime: 10);

        Assert.Contains(inactiveCarts, c => c.UserId == inactiveUser);
        Assert.DoesNotContain(inactiveCarts, c => c.UserId == activeUser);
    }

    [Fact]
    public void ClearCarts_RemovesProvidedCarts()
    {
        var repo = new CartsRepository();

        var u1 = Guid.NewGuid();
        var u2 = Guid.NewGuid();

        var c1 = repo.GetUsersCart(u1);
        var c2 = repo.GetUsersCart(u2);

        repo.ClearCarts(new List<Cart> { c1 });

        // c1 должен быть удалён, но при запросе создастся заново (новый объект)
        var c1new = repo.GetUsersCart(u1);

        Assert.NotSame(c1, c1new);
        Assert.Same(c2, repo.GetUsersCart(u2));
    }

    [Fact]
    public void UpdateCart_MovesLastUpdatedIntoFuture()
    {
        var repo = new CartsRepository();
        var userId = Guid.NewGuid();

        var cart = repo.GetUsersCart(userId);
        var before = cart.LastUpdated;

        repo.UpdateCart(userId);
        var after = repo.GetUsersCart(userId).LastUpdated;

        Assert.True(after > before);
        Assert.True(after > DateTime.Now);
    }
}