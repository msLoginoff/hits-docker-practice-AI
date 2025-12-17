using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
using Mockups.Storage;

namespace Mockups.Tests.TestSupport;

public static class SqliteTestDb
{
    public static (SqliteConnection Connection, ApplicationDbContext Db) Create()
    {
        var connection = new SqliteConnection("Filename=:memory:");
        connection.Open();

        var options = new DbContextOptionsBuilder<ApplicationDbContext>()
            .UseSqlite(connection)
            .Options;

        var db = new ApplicationDbContext(options);
        db.Database.EnsureCreated();

        return (connection, db);
    }
}