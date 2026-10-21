"""Decimal long-only accounting; weighted-average cost includes acquisition fees."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sentientalpha.backtesting.contracts import BacktestError

ZERO = Decimal(0)


@dataclass(slots=True)
class Position:
    quantity: Decimal = ZERO
    basis: Decimal = ZERO


class Ledger:
    def __init__(self, capital: Decimal):
        if not capital.is_finite() or capital <= 0:
            raise BacktestError("Positive finite initial equity required")
        self.initial = capital
        self.cash = capital
        self.positions: dict[str, Position] = {}
        self.realized = ZERO
        self.fees = ZERO
        self.slippage = ZERO
        self.dividends = ZERO
        self.closed: list[Decimal] = []

    def fill(
        self,
        ticker: str,
        side: str,
        quantity: Decimal,
        price: Decimal,
        fee: Decimal,
        slippage: Decimal = ZERO,
    ) -> Decimal:
        if (
            side not in {"buy", "sell"}
            or any(not x.is_finite() for x in (quantity, price, fee, slippage))
            or quantity <= 0
            or price <= 0
            or fee < 0
            or slippage < 0
        ):
            raise BacktestError("Invalid fill")
        current = self.positions.get(ticker, Position())
        notional = quantity * price
        if side == "buy":
            if notional + fee > self.cash:
                raise BacktestError("Insufficient cash")
            self.cash -= notional + fee
            current.basis += notional + fee
            current.quantity += quantity
            pnl = ZERO
        else:
            if quantity > current.quantity:
                raise BacktestError("Short selling disabled")
            removed = current.basis * quantity / current.quantity
            pnl = notional - fee - removed
            self.cash += notional - fee
            current.basis -= removed
            current.quantity -= quantity
            if not current.quantity:
                current.basis = ZERO
            self.realized += pnl
            self.closed.append(pnl)
        self.positions[ticker] = current
        self.fees += fee
        self.slippage += slippage
        if self.cash < 0 or current.quantity < 0 or current.basis < 0:
            raise AssertionError("Ledger invariant violated")
        return pnl

    def action(self, ticker: str, kind: str, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0 or kind not in {"split", "dividend"}:
            raise BacktestError("Invalid corporate action")
        position = self.positions.get(ticker)
        if position is None:
            return ZERO
        if kind == "split":
            position.quantity *= value
            return ZERO
        payment = position.quantity * value
        self.cash += payment
        self.dividends += payment
        return payment

    def value(self, prices: dict[str, Decimal]) -> dict[str, Any]:
        holdings = {}
        for ticker, position in self.positions.items():
            if position.quantity:
                if ticker not in prices:
                    raise BacktestError(
                        "Missing valuation for held security", "incomplete_valuation"
                    )
                holdings[ticker] = position.quantity * prices[ticker]
        market = sum(holdings.values(), ZERO)
        equity = self.cash + market
        basis = sum((p.basis for p in self.positions.values()), ZERO)
        unrealized = market - basis
        residual = equity - self.initial - self.realized - unrealized - self.dividends
        if abs(residual) > Decimal("0.00000001"):
            raise AssertionError("P&L reconciliation failed")
        return {
            "cash": str(self.cash),
            "market_value": str(market),
            "equity": str(equity),
            "realized_pnl": str(self.realized),
            "unrealized_pnl": str(unrealized),
            "dividends": str(self.dividends),
            "fees": str(self.fees),
            "slippage": str(self.slippage),
            "gross_exposure": float(market / equity) if equity else None,
            "net_exposure": float(market / equity) if equity else None,
            "reconciliation_residual": str(residual),
            "positions": {
                t: {
                    "quantity": str(p.quantity),
                    "cost_basis": str(p.basis),
                    "weight": float(holdings.get(t, ZERO) / equity) if equity else None,
                }
                for t, p in sorted(self.positions.items())
            },
        }
