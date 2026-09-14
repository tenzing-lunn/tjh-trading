# 04 — Glossary

Home: [[PROJECT_PLAN]]

*Shared vocabulary so future club members are never lost in the code, and finance terms are
never a barrier either way. Add terms as they come up.*

## Backtesting / our machine
- **Out-of-sample (OOS):** tested on data the strategy's parameters were NOT chosen on. The
  only honest test. In-sample results are how you fool yourself.
- **Walk-forward:** pick parameters on a TRAIN window, score on the next unseen TEST window,
  roll forward. Anti-curve-fitting.
- **Lookahead bias:** accidentally using future info to make a past decision. Our engine
  prevents it structurally: position at bar `t` is earned on bar `t+1` (`shift(1)`).
- **Curve-fitting / overfitting:** tuning a strategy until it fits past noise. Dies OOS.
- **Net of costs:** after subtracting spread + slippage + fees. The only verdict that counts.
- **bps (basis points):** 1 bps = 0.01%. Costs are quoted in bps. "3/1 bps" = 3 spread, 1 slippage.
- **Sharpe ratio:** return per unit of volatility. Higher = smoother ride for the return.
- **Max drawdown:** worst peak-to-trough loss. How much pain the strategy puts you through.
- **Buy-and-hold / benchmark:** just holding the asset. The bar every strategy must beat.

## Options (for the modeling layer)
- **Call / put:** right to buy / sell at a strike price by expiry.
- **Strike:** the price the option lets you transact at.
- **Expiry:** when the option dies.
- **Premium:** what you pay for the option.
- **Implied volatility (IV):** the market's expected future volatility, baked into the price.
  Higher IV = more expensive options.
- **The Greeks:** sensitivities of the option price —
  - **Delta:** to the stock price. **Theta:** to time (decay — works against buyers daily).
  - **Gamma:** how delta changes. **Vega:** to IV.
- **Theta decay:** an option loses value as time passes, all else equal. This is why you can
  be right on direction and still lose. Central to why naive options trading bleeds out.
- **Bid/ask spread:** gap between buy and sell price. Wide on options → assuming you fill at
  mid-price is the classic backtest lie.
