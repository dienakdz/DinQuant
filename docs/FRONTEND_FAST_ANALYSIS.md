# Fast Analysis Frontend Integration Notes

**`frontend/` in this open source warehouse only contains the build product `dist/`**, and the Vue source code is in the **private frontend warehouse** (see the root directory `.github/workflows/update-frontend.yml`). Therefore, components such as `FastAnalysisReport.vue` cannot be modified directly in this warehouse. They need to be adjusted in the private warehouse according to the following instructions.

## 1. Take profit/stop loss display is reversed (BUY/SELL)

### Backend convention (`/api/fast-analysis/analyze`)

- **`trading_plan.stop_loss` / `trading_plan.take_profit`** Already aligned with `decision`:
  - **BUY**: `stop_loss < current price < take_profit`
  - **SELL (empty)**: `take_profit < current price < stop_loss` (stop loss is above, take profit is below)
- **`indicators.trading_levels.suggested_stop_loss / suggested_take_profit`** is the **reference price for long orders** in the collector. It cannot be used directly as the "stop loss/take profit" lines on the interface during SELL, otherwise it will be geometrically opposite to the short order.

### Common front-end errors

- The first line is hardcoded to bind `trading_levels.suggested_stop_loss`, and the second line is bound to `suggested_take_profit`.
- Or reverse the `stop_loss` / `take_profit` ** tags ** ("stop loss" in the template is tied to `take_profit`).

### Recommended writing method (modify in private warehouse)

Only use **`data.trading_plan`** (or compatible fields **`stopLoss` / `takeProfit`**) returned by the interface:

```text
Stop loss (loss exit price): trading_plan.stop_loss (or stopLoss)
Take profit (profit target price): trading_plan.take_profit (or takeProfit)
```

Optional: According to `trading_plan.decision === 'SELL'`, add a sentence "Short order: Stop loss is above the current price, take profit is below the current price" next to the copy.

### API compatible fields (added in backend)

`trading_plan` additionally contains:

- `entryPrice`, `stopLoss`, `takeProfit`, `positionSizePct`
- `loss_exit_price`, `profit_target_price` (consistent with stop loss/take profit values, with clearer semantics)
- `decision`: consistent with the main result `decision`, which facilitates judgment within the component

There is another camel case at the root level: `trendOutlook`, `trendOutlookSummary` (the same content as `trend_outlook`, etc.).

## 2. "Future time period prediction" is not displayed

Backend fields:

- **`trend_outlook`**: Object, including `next_24h`, `next_3d`, `next_1w`, `next_1m` (each item contains `score`, `trend`, `strength`).
- **`trend_outlook_summary`**: One line readable summary (Chinese/English with `language`).
- If you go to **`/api/fast-analysis/analyze-legacy`**: `fast_analysis` also has the above fields; `overview.report` will append the **[Period Prediction]** paragraph; the top level also has `trend_outlook` / `trend_outlook_summary`.

### What the front end needs to do

- **Single rendering** of `trend_outlook` or `trend_outlook_summary` in the quick analysis results page (do not read only the `summary` text).
- If the request is for the legacy interface, please read **`data.fast_analysis.trend_outlook`** or the top-level **`data.trend_outlook`**. Do not assume that it is only under a certain nested path.

## 3. Self-check list

| Check items | Description |
|--------|------|
| Interface path | Confirm whether you are using `/analyze` or `/analyze-legacy`, and the field paths are consistent |
| Binding source | Whether stop loss/take profit comes from `trading_plan` instead of `trading_levels` |
| SELL Geometry | Empty units: `take_profit < current < stop_loss` |
| Cycle prediction | Whether the template contains `trend_outlook` or `trend_outlook_summary` |

After updating the private front-end repository, replace `frontend/dist/` of this repository through CI or manual packaging (see `update-frontend.yml`).
