# Local development setup

## Requirements

- Python 3.12 (3.11+ should work), Node.js 22+, npm, and optionally Docker Desktop with its Linux engine running.
- Local mode uses SQLite at `data/petrotwin.sqlite3`. Compose mode uses PostgreSQL in a named Docker volume.

## Local mode (Windows PowerShell)

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r ml_service/requirements.txt
Set-Location frontend
npm ci
Set-Location ..
```

Start and check both services:

```powershell
.\scripts\start-dev.ps1
.\scripts\health-check.ps1
```

Open `http://localhost:5173`; API docs are at `http://localhost:8000/docs`. Stop only the processes recorded by the start script with `.\scripts\stop-dev.ps1`. The SQLite database is retained across restarts.

`PETROTWIN_DATA_MODE` defaults to `field`: a fresh database has no wells, and the Field Data screen is the entry point. To use the synthetic demo wells during development, explicitly set `$env:PETROTWIN_DATA_MODE='simulation'` in the same PowerShell session before starting the backend. Do not use simulation mode for field-data validation.

Run the full Python suite with `python scripts/test_all.py`; build the frontend with `Push-Location frontend; npm run build; Pop-Location`.

## Browser end-to-end tests

From `frontend`, install Playwright's Chromium once with `npx playwright install chromium` (or use installed Google Chrome), then run `npm run test:e2e`. The suite starts Vite and FastAPI in explicitly configured simulation mode, uses an isolated temporary SQLite database and dedicated local ports, then stops both services and removes that test database. It covers the forecast/optimization/scenario/saved-run journey, history error/invalid-record handling, and well registration plus measured CSV ingestion.

## Compose mode

For safe Docker Desktop and PostgreSQL restart-persistence verification, follow [docker-verification.md](docker-verification.md). These steps never remove the database volume.

Copy `.env.example` to `.env`, replace the placeholder with a strong URL-safe local password, then run:

```powershell
docker compose up --build
```

Dashboard: `http://localhost:3000`; FastAPI docs: `http://localhost:8000/docs`. PostgreSQL is internal to Compose and stored in the `petrotwin_runtime_data` volume. Stop with `docker compose down`. **Do not use `docker compose down -v`** if you need to preserve the database. A clean startup initializes the application's tables automatically; no separate destructive migration step is required.

Run API/repository/physics tests in the built API image with:

```powershell
docker compose run --rm --no-deps ml-service python scripts/test_all.py
```

## Troubleshooting

- If local FastAPI reports PostgreSQL/psycopg errors, check `DATABASE_URL`; unset it to use the documented local SQLite default.
- If the UI cannot reach FastAPI, check `scripts/health-check.ps1`, port 8000, and `CORS_ORIGINS`.
- If Vite dependencies are missing, run `npm ci` in `frontend`.
- Compose requires Docker Desktop's Linux engine and all three `POSTGRES_*` variables from `.env`.
- All built-in telemetry and model data are synthetic. No field-data connector is configured.
