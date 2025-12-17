using Microsoft.Data.Sqlite;
using Mockups.Storage;

namespace Mockups.Tests.TestSupport;

public sealed class SqliteDbFixture : IAsyncDisposable
{
    private readonly SqliteConnection _connection;

    public ApplicationDbContext Db { get; }

    public SqliteDbFixture()
    {
        _connection = new SqliteConnection("Filename=:memory:");
        _connection.Open();

        Db = new ApplicationDbContext(SqliteTestDbOptions.Create(_connection));
        Db.Database.EnsureCreated();
    }

    public async ValueTask DisposeAsync()
    {
        await Db.DisposeAsync();
        await _connection.DisposeAsync();
    }
}