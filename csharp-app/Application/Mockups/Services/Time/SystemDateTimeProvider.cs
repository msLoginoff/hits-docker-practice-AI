namespace Mockups.Services.Time;

public sealed class SystemDateTimeProvider : IDateTimeProvider
{
    public DateTime Now => DateTime.Now;
}