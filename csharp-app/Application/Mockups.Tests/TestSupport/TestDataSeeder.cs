using Mockups.Storage;

namespace Mockups.Tests.TestSupport;

public static class TestDataSeeder
{
    public static async Task<User> AddUserAsync(
        ApplicationDbContext db,
        Guid userId,
        string name = "Test User")
    {
        var user = new User
        {
            Id = userId,

            // обязательные по твоей схеме
            Name = name,
            Phone = "+10000000000",

            // поля Identity (на случай NOT NULL в миграциях Identity)
            UserName = "test",
            NormalizedUserName = "TEST",
            Email = "test@test.local",
            NormalizedEmail = "TEST@TEST.LOCAL",
            SecurityStamp = Guid.NewGuid().ToString("N"),
            ConcurrencyStamp = Guid.NewGuid().ToString("N"),

            // если у User есть такое поле (IdentityUser)
            PhoneNumber = "+10000000000",
        };

        db.Users.Add(user);
        await db.SaveChangesAsync();

        return user;
    }

    public static async Task<MenuItem> AddMenuItemAsync(
        ApplicationDbContext db,
        Guid id,
        string name,
        int price,
        MenuItemCategory category,
        bool isVegan = false)
    {
        var item = new MenuItem
        {
            Id = id,
            Name = name,
            Description = "d",
            Price = price,
            Category = category,
            IsVegan = isVegan,
            PhotoPath = ""
        };

        db.MenuItems.Add(item);
        await db.SaveChangesAsync();

        return item;
    }
}