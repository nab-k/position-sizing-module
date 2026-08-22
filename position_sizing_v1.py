"""
Position sizing module.

Design:
- Instrument / PortfolioConfig are plain dataclasses -> typed, autocompletable,
  and match what a real market-data feed object would look like.
- Every sizer has the signature: sizer(instrument, config) -> int
  so they're interchangeable and composable.
- Capping is a decorator.
  It enforces (a) max amount per position and (b) min SL% per positionin one place.
"""

import math
from dataclasses import dataclass
from typing import Callable, Optional


# Data classes for instrument and portfolio config
@dataclass
class Instrument:
    symbol: str
    price: float
    sl_pct: Optional[float] = None   # e.g. 0.02 for 2%
    sl: Optional[float] = None       # absolute stop price, if known instead of sl_pct
    tp: Optional[float] = None

    @property
    def risk_per_share(self) -> float:
        """Rupee risk per share, derived from either sl_pct or an absolute sl."""
        if self.sl is not None:
            return abs(self.price - self.sl)
        if self.sl_pct is not None:
            return self.price * self.sl_pct
        raise ValueError(f"{self.symbol}: need either sl or sl_pct to size a position")

    @property
    def implied_sl_pct(self) -> float:
        return self.risk_per_share / self.price


@dataclass
class PortfolioConfig:
    portfolio_val: float
    partitions: int = 5                 # 'n' concurrent positions
    max_pct_risk: float = 0.01          # 1% of portfolio per trade
    fixed_risk_amt: float = 500.0       # hardcoded rupee risk per trade
    max_sl_pct: float = 0.02            # reject/cap trades with wider SL than this
    min_position_amt: float = 0.0       # optional floor, useful for pyramiding

    @property
    def max_position_amt(self) -> float:
        return self.portfolio_val / self.partitions

    @property
    def max_pct_risk_amt(self) -> float:
        return self.portfolio_val * self.max_pct_risk


# Type alias for sizing functions: accepts an Instrument and PortfolioConfig, returns an int
Sizer = Callable[[Instrument, PortfolioConfig], int]


# Capping — applied as a decorator around any sizer
def cap_position(sizer: Sizer) -> Sizer:
    """
    Wrap a sizer so every strategy automatically gets:
      - a hard cap on rupee amount per position (config.max_position_amt)
      - a reject/cap on positions whose SL% is too wide to size safely
    This is where your qty3a1 / qty3a2 / qty3a3 cases live, in one place
    instead of being duplicated inside each sizing function.
    """
    def wrapped(instrument: Instrument, config: PortfolioConfig) -> int:
        if instrument.implied_sl_pct > config.max_sl_pct:
            return 0

        qty = sizer(instrument, config)

        max_amt = config.max_position_amt
        if qty * instrument.price > max_amt:
            qty = math.floor(max_amt / instrument.price)

        return max(qty, 0)
    return wrapped


# Primitive Sizing strategies (all uncapped internally — handled by cap_position)
@cap_position
def fixed_amount(instrument: Instrument, config: PortfolioConfig) -> int:
    """Fixed rupee amount of portfolio per entry."""
    return math.floor(config.max_position_amt / instrument.price)


@cap_position
def pct_risk(instrument: Instrument, config: PortfolioConfig) -> int:
    """Fixed % of portfolio value risked, sized off SL distance."""
    return math.floor(config.max_pct_risk_amt / instrument.risk_per_share)


@cap_position
def fixed_risk(instrument: Instrument, config: PortfolioConfig) -> int:
    """Fixed rupee amount risked (e.g. 500), sized off SL distance."""
    return math.floor(config.fixed_risk_amt / instrument.risk_per_share)


# For dynamic use of Primitive Sizing strategies in a GUI or config file - unused by default
SIZERS: dict[str, Sizer] = {
    "fixed_amount": fixed_amount,
    "pct_risk": pct_risk,
    "fixed_risk": fixed_risk,
}


# Pyramiding — built on top of a base sizer, with a weight list to split the base quantity across multiple entries
def pyramid_quantities(base_qty: int, weights: list[float]) -> list[int]:
    """
    Split a base quantity across pyramid entries using relative weights for a reverse-pyramid entry schedule.
    """
    total_weight = sum(weights)
    return [math.floor(base_qty * w / total_weight) for w in weights]


# Example usage
if __name__ == "__main__":
    portfolio_config = PortfolioConfig(portfolio_val=100_000, partitions=5,
                              max_pct_risk=0.01, fixed_risk_amt=500)

    xyz = Instrument(symbol="XYZ", price=150, sl_pct=0.02)

    print("fixed_amount:", fixed_amount(xyz, portfolio_config))
    print("pct_risk:    ", pct_risk(xyz, portfolio_config))
    print("fixed_risk:  ", fixed_risk(xyz, portfolio_config))

    # SL too far away
    risky = Instrument(symbol="RISKY", price=100, sl_pct=0.05)
    print("fixed_risk (wide SL, rejected):", fixed_risk(risky, portfolio_config))

    # pyramid entries
    print("pyramid split:", pyramid_quantities(100, [5, 4, 3, 2, 1]))