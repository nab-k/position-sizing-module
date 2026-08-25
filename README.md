# Trade Position Sizing

A single-file Python module for calculating trade position sizes,
built primarily as a **hands-on exercise in Python OOP and functional
patterns** — dataclasses, decorators, `Callable` type aliases, and
dictionary-based dispatch — rather than as a serious finance tool.


> **Disclaimer:** This is a learning project for practicing Python OOP
> concepts, not a production risk-management system. The sizing math is
> intentionally simple (no slippage, lot sizes, leverage, or commissions)
> and nothing here should be used to size real trades without your own
> independent risk management.

---

## Contents

| Component | Purpose |
|---|---|
| `Instrument` | Dataclass representing a tradeable instrument (price, stop-loss, target). |
| `PortfolioConfig` | Dataclass representing account/portfolio-level sizing rules. |
| `cap_position` | Decorator that wraps any sizer with a shared position-cap + SL-rejection rule. |
| `fixed_amount`, `pct_risk`, `fixed_risk` | Three interchangeable sizing strategies, each decorated with `cap_position`. |
| `SIZERS` | Dict mapping strategy names to functions, for dynamic lookup (e.g. from a config file or GUI). |
| `pyramid_quantities` | Splits a base quantity across multiple pyramided entries using relative weights. |

Everything lives in `position_sizing_v1.py` — there's no package
structure yet since the project is small enough that it wasn't worth it.

---

## Concepts Demonstrated

This project was written to practice, specifically:

- **Dataclasses with computed properties** — `Instrument.risk_per_share`
  and `Instrument.implied_sl_pct`, `PortfolioConfig.max_position_amt`
  and `.max_pct_risk_amt` are all derived from stored fields via
  `@property`, so they can never drift out of sync with the underlying
  data.
- **Decorators as cross-cutting concerns** — `cap_position` implements
  the "reject if SL is too wide" and "cap the position value" rules
  *once*, and every sizing strategy gets them for free just by being
  wrapped, instead of duplicating that logic inside each function.
- **`Callable` type aliases as a lightweight Strategy pattern** — the
  `Sizer = Callable[[Instrument, PortfolioConfig], int]` alias means any
  function with that signature is interchangeable. This gets you most of
  the benefit of a `Strategy` interface/ABC without the class ceremony.
- **Dictionary dispatch** — `SIZERS` maps strings to functions, so a
  strategy can be selected dynamically (e.g. from user input or a config
  file) instead of a long `if/elif` chain.
- **Composition over branching** — three separate, small sizing
  functions instead of one function with a `mode` argument and a wall of
  conditionals.

---

## Installation

Requires Python 3.9+ (uses the `dict[str, Sizer]` built-in generic
syntax). No external dependencies — standard library only.

```bash
git clone <this-repo-url>
cd <repo-folder>
python3 position_sizing_v1.py
```

---

## Usage

### As a script

Running the file directly executes the example block at the bottom,
which builds a sample portfolio and instrument and prints the result of
each sizing strategy:

```bash
python3 position_sizing_v1.py
```

```
fixed_amount: 133
pct_risk:     133
fixed_risk:   133
fixed_risk (wide SL, rejected): 0
pyramid split: [33, 26, 20, 13, 6]
```

In this example (₹100,000 portfolio, 5 partitions, XYZ instrument at ₹150 with a 2%
SL), all three strategies happen to converge on the same quantity
because each one's "natural" size is larger than the per-position cap
(`portfolio_val / partitions` = ₹20,000), so `cap_position` clips them
all down to the same number. This is a good illustration of the
decorator actually doing its job — try loosening `partitions` or
`max_pct_risk` to see the strategies diverge.

### As a module

```python
from position_sizing_v1 import Instrument, PortfolioConfig, pct_risk, SIZERS

config = PortfolioConfig(portfolio_val=100_000, partitions=5, max_pct_risk=0.01)
instrument = Instrument(symbol="XYZ", price=150, sl_pct=0.02)

qty = pct_risk(instrument, config)          # call a strategy directly
qty = SIZERS["fixed_risk"](instrument, config)  # or look it up dynamically
```

### How sizing works

1. Each raw sizer (`fixed_amount`, `pct_risk`, `fixed_risk`) computes a
   quantity from first principles — no capping logic inside them.
2. `cap_position` wraps every sizer and:
   - rejects the trade outright (`return 0`) if `implied_sl_pct` is
     wider than `config.max_sl_pct`,
   - otherwise runs the sizer, then floors the quantity so its rupee
     value never exceeds `config.max_position_amt`.
3. `pyramid_quantities` is a separate helper — it takes a base quantity
   (e.g. the output of one of the sizers above) and splits it across
   several entries by relative weight, for scaling into a position
   rather than entering all at once.

---

## Known Limitations

- `min_position_amt` on `PortfolioConfig` is declared but not currently
  enforced anywhere in `cap_position` — it's a placeholder for a future
  pyramiding floor, not a working feature yet.
- `Instrument.risk_per_share` raises `ValueError` if neither `sl` nor
  `sl_pct` is set — there's no default/fallback behavior.
- No handling of lot sizes, minimum tick sizes, leverage/margin, or
  transaction costs — quantities are pure `portfolio_val / price` math.
- No tests yet — the `__main__` block is a manual smoke test, not a
  test suite.
- No CLI or config-file input; `SIZERS` exists for that purpose but
  nothing currently drives it dynamically.

---
## Roadmap

This is an early, single-file learning project, not a finished tool.
Expect it to grow over time as more pieces get built out — broker/API
integration for live prices and order placement, additional sizing
strategies, real handling of lot sizes and margin, config-driven
strategy selection via `SIZERS`, and tests. The OOP patterns here
are meant to be a foundation that new pieces slot into.
