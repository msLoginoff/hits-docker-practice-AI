namespace Mockups.Services.Time;

public interface IDateTimeProvider
{
    DateTime Now { get; }
}