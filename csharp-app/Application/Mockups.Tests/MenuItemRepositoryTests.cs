using Microsoft.EntityFrameworkCore;
using Mockups.Repositories.MenuItems;
using Mockups.Storage;

namespace Mockups.Tests;

public class MenuItemRepositoryTests
{
    private static ApplicationDbContext CreateContext()
    {
        var options = new DbContextOptionsBuilder<ApplicationDbContext>()
            .UseInMemoryDatabase(Guid.NewGuid().ToString())
            .Options;

        return new ApplicationDbContext(options);
    }

    [Fact]
    public async Task AddItem_ThenGetItemById_ReturnsItem()
    {
        await using var ctx = CreateContext();
        var repo = new MenuItemRepository(ctx);

        var id = Guid.NewGuid();
        var item = new MenuItem
        {
            Id = id,
            Name = "Test",
            Description = "Desc",
            Price = 10,
            Category = MenuItemCategory.Pizza,
            IsVegan = false,
            PhotoPath = "x"
        };

        await repo.AddItem(item);

        var found = await repo.GetItemById(id);

        Assert.NotNull(found);
        Assert.Equal("Test", found!.Name);
    }

    [Fact]
    public async Task DeleteItem_MarksIsDeleted_AndExcludesFromGetAllMenuItems()
    {
        await using var ctx = CreateContext();
        var repo = new MenuItemRepository(ctx);

        var item = new MenuItem
        {
            Id = Guid.NewGuid(),
            Name = "ToDelete",
            Description = "Desc",
            Price = 10,
            Category = MenuItemCategory.WOK,
            IsVegan = true,
            PhotoPath = "x"
        };

        await repo.AddItem(item);
        await repo.DeleteItem(item);

        var all = await repo.GetAllMenuItems();
        Assert.DoesNotContain(all, x => x.Id == item.Id);

        var byId = await repo.GetItemById(item.Id);
        Assert.Null(byId);
    }

    [Fact]
    public async Task GetAllMenuItems_FilterByVeganAndCategory_Works()
    {
        await using var ctx = CreateContext();
        var repo = new MenuItemRepository(ctx);

        await repo.AddItem(new MenuItem
        {
            Id = Guid.NewGuid(), Name = "VeganPizza", Description = "d", Price = 1,
            Category = MenuItemCategory.Pizza, IsVegan = true, PhotoPath = "x"
        });

        await repo.AddItem(new MenuItem
        {
            Id = Guid.NewGuid(), Name = "MeatPizza", Description = "d", Price = 1,
            Category = MenuItemCategory.Pizza, IsVegan = false, PhotoPath = "x"
        });

        await repo.AddItem(new MenuItem
        {
            Id = Guid.NewGuid(), Name = "VeganSoup", Description = "d", Price = 1,
            Category = MenuItemCategory.Soup, IsVegan = true, PhotoPath = "x"
        });

        var res = await repo.GetAllMenuItems(true, new[] { MenuItemCategory.Pizza });

        Assert.Single(res);
        Assert.Equal("VeganPizza", res[0].Name);
    }
    
    [Fact]
    public async Task GetItemByName_ReturnsNull_WhenDeleted()
    {
        await using var ctx = CreateContext();
        var repo = new MenuItemRepository(ctx);

        var item = new MenuItem
        {
            Id = Guid.NewGuid(),
            Name = "X",
            Description = "d",
            Price = 1,
            Category = MenuItemCategory.Pizza,
            IsVegan = false,
            PhotoPath = ""
        };

        await repo.AddItem(item);
        await repo.DeleteItem(item);

        var found = await repo.GetItemByName("X");
        Assert.Null(found);
    }
}