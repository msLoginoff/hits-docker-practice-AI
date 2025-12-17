using Mockups.Services.Time;

namespace Mockups.Tests.TestSupport;

public sealed class FakeDateTimeProvider : IDateTimeProvider
{
    public DateTime Now { get; set; }
}