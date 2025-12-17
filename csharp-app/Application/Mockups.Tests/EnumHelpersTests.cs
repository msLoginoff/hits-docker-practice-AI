using Mockups.Storage;

namespace Mockups.Tests;

public class EnumHelpersTests
{
    [Fact]
    public void MenuItemCategory_GetDisplayName_ReturnsRussianName()
    {
        Assert.Equal("Пицца", MenuItemCategory.Pizza.GetDisplayName());
        Assert.Equal("Вок", MenuItemCategory.WOK.GetDisplayName());
    }

    [Fact]
    public void OrderStatus_Next_Works()
    {
        Assert.Equal(OrderStatus.InProcess, OrderStatus.New.Next());
        Assert.Equal(OrderStatus.Ready, OrderStatus.InProcess.Next());
        Assert.Equal(OrderStatus.Delivered, OrderStatus.Ready.Next());
        Assert.Null(OrderStatus.Delivered.Next());
    }
}