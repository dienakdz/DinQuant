# QuantDinger Web UI (Vue 2)

This `frontend_vue` folder was restored from the last public frontend source commit in `brokermr810/QuantDinger`:

- Source baseline: `ffdd2ff` on February 27, 2026
- Frontend became closed-source at: `abbad97` on February 27, 2026
- Current bundled frontend in this repo: [`frontend/dist`](/e:/DinQuant/frontend/dist) version `3.0.1`

This means `frontend_vue` is the closest full editable source available from git history. It builds successfully locally, but it is not guaranteed to be byte-for-byte identical to the newer private `frontend/dist` bundle.

This is the QuantDinger frontend web UI built with **Vue 2** + **Ant Design Vue**. It connects to the Python backend (`backend_api_python/`) through HTTP APIs to provide charts, indicators, backtests, AI analysis, and strategy management.

> This UI is based on the open-source `ant-design-vue-pro` ecosystem, heavily adapted for QuantDinger.

## What you get

- **Dashboards**: summary views and operational panels
- **Indicator analysis**: Kline charts + indicator editing + backtest history
- **AI analysis**: multi-agent reports (optional LLM/search, configured on backend)
- **Trading assistant**: strategy lifecycle + positions/records (depending on backend capability)
- **Local auth**: login with backend-configured admin credentials

## Quick start (local development)

### Prerequisites

- Node.js 16+ recommended
- Backend running at `http://localhost:5000` (see `backend_api_python/README.md`)

### 1) Install dependencies

```bash
cd frontend_vue
corepack yarn install --ignore-engines
```

### 2) Start dev server

```bash
corepack yarn serve
```

Dev server runs at `http://localhost:8000`.

### 3) API proxy (important)

In dev mode, this project proxies `/api/*` to the backend:

- Proxy config: `frontend_vue/vue.config.js`
- Default target: `http://localhost:5000`

If your backend runs on a different host/port, update `vue.config.js` accordingly.

## Production build

```bash
corepack yarn build
```

The output will be generated under `frontend_vue/dist/`.

## Notes

- **CORS**: when using the dev proxy, you typically don’t need extra CORS config.
- **Login**: use the credentials defined in `backend_api_python/.env` (`ADMIN_USER` / `ADMIN_PASSWORD`).

## License

Apache License 2.0. See repository root `LICENSE`.
