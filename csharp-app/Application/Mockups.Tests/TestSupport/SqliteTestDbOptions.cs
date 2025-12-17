using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
using Mockups.Storage;

namespace Mockups.Tests.TestSupport;

public static class SqliteTestDbOptions
{
    public static DbContextOptions<ApplicationDbContext> Create(SqliteConnection connection) =>
        new DbContextOptionsBuilder<ApplicationDbContext>()
            .UseSqlite(connection)
            .Options;
}