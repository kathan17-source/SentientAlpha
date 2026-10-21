"""One opening attempt per market order; unfilled remainder canceled (IOC)."""

from datetime import datetime
from decimal import ROUND_FLOOR, Decimal
from typing import Any

from sentientalpha.backtesting.contracts import Costs
from sentientalpha.backtesting.ledger import ZERO, Ledger


def commission(costs: Costs, quantity: Decimal, price: Decimal) -> Decimal:
    return costs.fixed + costs.per_share * quantity + costs.percentage * quantity * price


def execute(
    ledger: Ledger,
    order: dict[str, Any],
    opening: Decimal | None,
    previous_volume: int | None,
    at: datetime,
    costs: Costs,
    marks: dict[str, Decimal],
    used: Decimal = ZERO,
) -> dict[str, Any] | None:
    reason = None
    requested = Decimal(order["requested_quantity"])
    quantity = requested
    side, ticker = order["side"], order["ticker"]
    if (
        datetime.fromisoformat(order["earliest_execution_at"]) > at
        or datetime.fromisoformat(order["submitted_at"]) >= at
    ):
        reason = "information_not_ready"
    elif opening is None or not opening.is_finite() or opening <= 0:
        reason = "missing_open_or_suspended"
    elif previous_volume is None and costs.unknown_volume == "reject":
        reason = "missing_prior_volume"
    elif previous_volume is not None and previous_volume < costs.minimum_volume:
        reason = "insufficient_prior_volume"
    if reason:
        order.update(status="rejected", reason=reason)
        return None
    assert opening is not None
    if previous_volume is not None:
        quantity = min(
            quantity,
            max(
                ZERO,
                (Decimal(previous_volume) * costs.participation).to_integral_value(
                    rounding=ROUND_FLOOR
                )
                - used,
            ),
        )
    price = opening * (1 + (1 if side == "buy" else -1) * costs.slippage_bps / 10000)
    if side == "buy":
        affordable = max(
            ZERO,
            (
                (ledger.cash - costs.fixed) / (price * (1 + costs.percentage) + costs.per_share)
            ).to_integral_value(rounding=ROUND_FLOOR),
        )
        equity = Decimal(ledger.value(marks)["equity"])
        held = ledger.positions.get(ticker)
        capacity = max(
            ZERO,
            (
                (
                    (equity - costs.fixed) * costs.position_limit
                    - (held.quantity * opening if held else ZERO)
                )
                / (
                    opening
                    + costs.position_limit
                    * (price - opening + costs.per_share + costs.percentage * price)
                )
            ).to_integral_value(rounding=ROUND_FLOOR),
        )
        quantity = min(quantity, affordable, capacity)
    else:
        position = ledger.positions.get(ticker)
        quantity = min(quantity, position.quantity if position else ZERO)
    if quantity < costs.minimum_quantity:
        order.update(status="rejected", reason="cash_position_liquidity_or_minimum_constraint")
        return None
    fee = commission(costs, quantity, price)
    if side == "buy":
        post_equity = Decimal(ledger.value(marks)["equity"]) - fee - quantity * abs(price - opening)
        if any(
            t != ticker and p.quantity * marks[t] > costs.position_limit * post_equity
            for t, p in ledger.positions.items()
            if p.quantity
        ):
            order.update(status="rejected", reason="other_position_post_cost_limit")
            return None
    if side == "sell" and quantity * price - fee < 0:
        order.update(status="rejected", reason="fees_exceed_proceeds")
        return None
    slip = quantity * abs(price - opening)
    pnl = ledger.fill(ticker, side, quantity, price, fee, slip)
    fill = {
        "id": order["id"] + "-fill",
        "order_id": order["id"],
        "ticker": ticker,
        "side": side,
        "quantity": str(quantity),
        "price": str(price),
        "raw_open": str(opening),
        "commission": str(fee),
        "slippage": str(slip),
        "at": at.isoformat(),
        "realized_pnl": str(pnl),
    }
    order.update(
        status="filled" if quantity == requested else "partial_canceled",
        filled_quantity=str(quantity),
        remaining_quantity=str(requested - quantity),
        execution_at=at.isoformat(),
        execution_price=str(price),
        commission=str(fee),
        slippage=str(slip),
        reason=None if quantity == requested else "constrained_remainder_canceled",
    )
    return fill
