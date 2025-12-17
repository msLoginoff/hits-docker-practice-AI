using System.Text;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.FileProviders;
using Moq;
using Mockups.Models.Menu;
using Mockups.Repositories.MenuItems;
using Mockups.Services.Carts;
using Mockups.Services.MenuItems;
using Mockups.Storage;
using Mockups.Tests.TestSupport;

namespace Mockups.Tests;

public class MenuItemsServiceTests
{
    [Fact]
    public async Task CreateMenuItem_Throws_WhenNameDuplicate()
    {
        var (conn, db) = SqliteTestDb.Create();
        await using var _ = db;
        await using var __ = conn;

        db.MenuItems.Add(new MenuItem
        {
            Name = "Same",
            Description = "d",
            Price = 1,
            Category = MenuItemCategory.Pizza,
            IsVegan = false,
            PhotoPath = ""
        });
        await db.SaveChangesAsync();

        var repo = new MenuItemRepository(db);
        var env = FakeEnv();
        var carts = new Mock<ICartsService>();

        var svc = new MenuItemsService(env, repo, carts.Object);

        await Assert.ThrowsAsync<ArgumentException>(() =>
            svc.CreateMenuItem(new CreateMenuItemViewModel
            {
                Name = "Same",
                Description = "d",
                Price = 2,
                Category = MenuItemCategory.Soup,
                IsVegan = true,
                File = null!
            }));
    }

    [Fact]
    public async Task CreateMenuItem_Throws_WhenFileExtensionNotAllowed()
    {
        var (conn, db) = SqliteTestDb.Create();
        await using var _ = db;
        await using var __ = conn;

        var repo = new MenuItemRepository(db);
        var env = FakeEnv();
        var carts = new Mock<ICartsService>();

        var svc = new MenuItemsService(env, repo, carts.Object);

        var file = MakeFile("pic.gif", "data");

        await Assert.ThrowsAsync<ArgumentException>(() =>
            svc.CreateMenuItem(new CreateMenuItemViewModel
            {
                Name = "X",
                Description = "d",
                Price = 2,
                Category = MenuItemCategory.Soup,
                IsVegan = true,
                File = file
            }));
    }

    [Fact]
    public async Task CreateMenuItem_SavesFile_AndPersistsItem()
    {
        var (conn, db) = SqliteTestDb.Create();
        await using var _ = db;
        await using var __ = conn;

        var repo = new MenuItemRepository(db);

        var webRoot = Path.Combine(Path.GetTempPath(), "mockups-tests-" + Guid.NewGuid());
        Directory.CreateDirectory(webRoot);
        Directory.CreateDirectory(Path.Combine(webRoot, "files"));

        var env = FakeEnv(webRoot);
        var carts = new Mock<ICartsService>();
        var svc = new MenuItemsService(env, repo, carts.Object);

        var file = MakeFile("photo.PNG", "hello"); // проверяем case-insensitive

        await svc.CreateMenuItem(new CreateMenuItemViewModel
        {
            Name = "Item1",
            Description = "d",
            Price = 10,
            Category = MenuItemCategory.Pizza,
            IsVegan = false,
            File = file
        });

        var saved = (await repo.GetItemByName("Item1"))!;
        Assert.NotNull(saved);
        Assert.StartsWith("files/", saved.PhotoPath);
        Assert.EndsWith("-photo.PNG", saved.PhotoPath);

        var diskPath = Path.Combine(webRoot, saved.PhotoPath);
        Assert.True(File.Exists(diskPath));

        Directory.Delete(webRoot, recursive: true);
    }

    [Fact]
    public async Task GetAllMenuItems_DoesNotThrow_WhenCategoryNull()
    {
        var (conn, db) = SqliteTestDb.Create();
        await using var _ = db;
        await using var __ = conn;

        db.MenuItems.Add(new MenuItem
        {
            Name = "A",
            Description = "d",
            Price = 1,
            Category = MenuItemCategory.Pizza,
            IsVegan = true,
            PhotoPath = ""
        });
        await db.SaveChangesAsync();

        var repo = new MenuItemRepository(db);
        var env = FakeEnv();
        var carts = new Mock<ICartsService>();
        var svc = new MenuItemsService(env, repo, carts.Object);

        var items = await svc.GetAllMenuItems(null, null);

        Assert.Single(items);
        Assert.Equal("A", items[0].Name);
    }

    private static IFormFile MakeFile(string fileName, string content)
    {
        var bytes = Encoding.UTF8.GetBytes(content);
        var stream = new MemoryStream(bytes);

        return new FormFile(stream, 0, bytes.Length, "file", fileName);
    }

    private static IWebHostEnvironment FakeEnv(string? webRoot = null)
    {
        webRoot ??= Path.Combine(Path.GetTempPath(), "mockups-tests-" + Guid.NewGuid());
        Directory.CreateDirectory(webRoot);

        return new FakeWebHostEnvironment
        {
            WebRootPath = webRoot,
            WebRootFileProvider = new PhysicalFileProvider(webRoot),
            ContentRootPath = webRoot,
            ContentRootFileProvider = new PhysicalFileProvider(webRoot),
            ApplicationName = "Mockups.Tests",
            EnvironmentName = "Testing"
        };
    }

    private sealed class FakeWebHostEnvironment : IWebHostEnvironment
    {
        public string ApplicationName { get; set; } = "";
        public IFileProvider ContentRootFileProvider { get; set; } = default!;
        public string ContentRootPath { get; set; } = "";
        public string EnvironmentName { get; set; } = "Testing";

        public string WebRootPath { get; set; } = "";
        public IFileProvider WebRootFileProvider { get; set; } = default!;
    }
}