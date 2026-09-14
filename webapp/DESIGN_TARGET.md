# Web App — Visual Design Target

Home: [[PROJECT_PLAN]] · Spec: [[webapp/SPEC]] · Mockup: `webapp/MOCKUP.html` (open in a browser)

*The current UI is functional but ugly. `MOCKUP.html` is the look we're building toward.
Build the real components to match it. Every number stays computed in Python (`api_server.py`),
never in JS — the mockup's values are illustrative only.*

## The four panels (build/restyle in this order)
1. **Price + signal overlay.** Line chart of adjusted price. Background shaded by position:
   green = long, grey = flat (red = short when used). ▲ buy / ▼ sell markers where trades fire.
2. **Pay-per-trade simulator.** Three equity curves on one axis: strategy *after costs* (red),
   buy-and-hold (green), SPY (dashed grey). The teaching moment is the red line sinking below
   the others. Driven by the cost sliders.
3. **Cost sliders.** Spread / slippage / fee. Dragging re-requests a run from the harness and
   redraws panels 1, 2, 4 live. This is the "feel why costs kill edges" interaction.
4. **Verdict panel.** Big REAL/DEAD badge + OOS-net-of-costs return, buy-and-hold comparison,
   Sharpe, max drawdown, trades, win rate — straight from `metrics.py`. Plus a display-only
   live quote (clearly "not a recommendation").
5. **Robustness / red-flag panel.** Per-year return bars + an auto-generated list of
   plain-English red flags ("82% of return came from 2020", "only 11 trades/fold — Sharpe may be
   luck", "best of 12 configs — deflated Sharpe ~0.2"). Lets a non-expert SEE why a result might
   be fake. Computed in Python (`diagnostics.py` — see [[plan/10-verdict-and-diagnostics-spec]]).
   The flag is a prompt to look closer, NOT the verdict — the advance/kill call stays human.

## Visual language
Flat, clean, lots of whitespace. Light theme. Greens for "good/long," reds for "after-cost
reality/dead." No gradients or chart-junk. Tabular numerals for all metrics. Mobile: panels
stack to one column.

## Hard rules (from SPEC, do not break)
- No backtest math in JavaScript. Need a number? Add it to the Python payload.
- No order execution in the app. Display only.
- Real-ticker price data stays out of public commits (vendor terms).
