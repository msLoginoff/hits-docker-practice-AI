using System.Reflection;
using Mockups.Configs;
using Mockups.Repositories.Carts;
using Mockups.Services.CartsCleanerService;

namespace Mockups.Tests;

public class CartsCleanerTests
{
    [Fact]
    public void DoWork_RemovesInactiveCarts_ByConfigTime()
    {
        var repo = new CartsRepository();
        var config = new CartsCleanerConfig { Time = 10 }; // минут

        var activeUser = Guid.NewGuid();
        var inactiveUser = Guid.NewGuid();

        repo.GetUsersCart(activeUser).LastUpdated = DateTime.Now;
        repo.GetUsersCart(inactiveUser).LastUpdated = DateTime.Now.AddMinutes(-30);

        var cleaner = new CartsCleaner(config, repo);

        // приватный метод DoWork дергаем через reflection
        var doWork = typeof(CartsCleaner).GetMethod("DoWork", BindingFlags.NonPublic | BindingFlags.Instance);
        Assert.NotNull(doWork);

        doWork!.Invoke(cleaner, new object?[] { null });

        var inactiveCarts = repo.GetInactiveCarts(10);
        Assert.DoesNotContain(inactiveCarts, c => c.UserId == inactiveUser);
    }
}