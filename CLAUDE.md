# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`cr_stats` analyzes the top Clash Royale ladder players. A scheduled job pulls battle logs from the Clash Royale API, aggregates the most-used cards and decks, and writes JSON snapshots to Postgres. A small Flask-RESTful API serves the latest snapshot to a React frontend.

A valid Clash Royale API key (`API_KEY` in `.env`, alongside `DB_HOST`/`DB_NAME`/`DB_USER`/`DB_PASSWORD`) is required for any data refresh — the IP allowlisted on the key must match wherever you run `update_cards.py`.

## Commands

The Makefile drives the full lifecycle through `docker-compose`:

- `make init` — first-time setup: bring up the stack, create tables, run an initial data pull.
- `make up` — start backend / postgres / nginx (`docker-compose --env-file .env up -d`).
- `make migrate` — create/migrate the relational tables (`cards`, `decks`, `players`, `battles`) — idempotent.
- `make update-cards` — refresh data by hitting the Clash Royale API for the top 100 players.

Other useful invocations:

- Backend tests: `docker-compose exec backend python -m unittest backend/tests/test_sanity.py` (the test suite is currently a single sanity test).
- Frontend dev server: `cd frontend && npm start` (serves on `:3000`, hits backend at `http://localhost:5001`).
- Frontend production build: `cd frontend && npm run build` — nginx (in the `server` container) serves `frontend/build` via a bind mount, so you must rebuild before changes appear in the dockerized stack.

## Architecture

### Data flow

1. `scripts/update_cards.py` is the cron-style entry point. It calls `scripts/utils/data_utils.py` to fetch the latest season ID, the top N player tags, and each player's battle log (parallelized via a 20-worker `ThreadPoolExecutor`).
2. Battle data is filtered to `pathOfLegend` battles and written into a relational schema: `cards`, `decks`, `players`, and `battles` tables (created/migrated via `make migrate`).
3. Flask-RESTful resources mounted in `app.py` at `/cards`, `/decks`, `/battles`, and `/player/<tag>` query the relational tables at request time and hydrate deck/card data via `apis/utils/decks.py:hydrate_deck`.

There is no API-time call to the Clash Royale API — all data comes from the relational tables populated by `make update-cards`. To change what's served, change the aggregation in `data_utils.py` and re-run `make update-cards`.

### Backend layout / import conventions

The backend Dockerfile sets `WORKDIR /usr/src/` and `PYTHONPATH` includes `/usr/src/cr_stats`, and gunicorn runs `app:app` from that dir. Internal imports therefore use top-level package names rooted at `backend/` (e.g. `from apis.utils.db_utils import make_connection`, `from scripts.utils.data_utils import ...`, `from settings import TZ`) — not `backend.apis...`. Match this style in new files.

`settings.py` loads `.env` from the repo root (`..` from `backend/`) and is the single source for `API_KEY`, `API_URL`, `HEADERS`, DB credentials, and the `TZ` (UTC) timezone. `db_utils.make_connection()` is the only place psycopg2 connects — reuse it via `with make_connection() as connection:`.

### Frontend

Create-React-App (react-scripts 5) with `react-router` v7. `index.js` mounts two routes — `/` renders `<App component={TopCards} />` and `/decks` renders `<App component={TopDecks} />`; `App.js` is a shared chrome that injects whichever child component was passed via props. Both `TopCards` and `TopDecks` are class components that fetch from a hardcoded `http://localhost:5001/...` in `componentDidMount` — update this URL when changing backend host/port.

### Deployment topology (`docker-compose.yml`)

- `backend` — gunicorn on `:5001`, source bind-mounted from `./backend` (so code edits hot-reload via gunicorn `--reload`).
- `postgres` — Postgres 17.5 with a named volume `postgres_data`.
- `server` — nginx (config at `server/default.conf`) serving the static React build from `frontend/build`, bound to ports 80/443. Server name is `cr.matthewmyoung.com`.

All three share the `cr_stats` bridge network; backend reaches postgres via `DB_HOST=postgres`.
