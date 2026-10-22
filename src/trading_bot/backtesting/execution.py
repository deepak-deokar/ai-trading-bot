"""OHLC reachability at completion; eligible orders predate execution-bar opening."""

from decimal import Decimal

from trading_bot.backtesting.orders import OrderType, Side, SimOrder
from trading_bot.backtesting.slippage import SlippageModel
from trading_bot.domain.models import Bar


def base_price(order: SimOrder, bar: Bar) -> Decimal | None:
    intent = order.intent
    if intent.order_type == OrderType.MARKET or any(
        t.status.value == "TRIGGERED" for t in order.transitions
    ):
        return bar.open
    if intent.order_type == OrderType.LIMIT:
        assert intent.limit_price is not None
        if intent.side == Side.BUY and bar.low <= intent.limit_price:
            return min(bar.open, intent.limit_price)
        if intent.side == Side.SELL and bar.high >= intent.limit_price:
            return max(bar.open, intent.limit_price)
    else:
        assert intent.trigger_price is not None
        if intent.side == Side.BUY and bar.high >= intent.trigger_price:
            return max(bar.open, intent.trigger_price)
        if intent.side == Side.SELL and bar.low <= intent.trigger_price:
            return min(bar.open, intent.trigger_price)
    return None


def execution_price(order: SimOrder, base: Decimal, slippage: SlippageModel) -> Decimal:
    price = slippage.apply(base, order.intent.side)
    limit = order.intent.limit_price
    if limit is not None:
        price = (
            min(price, limit) if order.intent.side == Side.BUY else max(price, limit)
        )
    return price
