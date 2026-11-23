# Docker Desktop and PostgreSQL local verification

> **Historical snapshot:** This records an earlier field-mode Docker verification run before the final authentication, agent-runtime, and measured-data ML changes. Its 58 Python tests and 6 browser E2E tests are historical results, not the latest-source totals. The consolidated latest-source results (80 Python tests and 7 browser E2E tests), and the outstanding latest-source Docker rebuild, are recorded in [integration-status.md](integration-status.md).

## Verified locally

On 2026-11-23, the Compose application was built and started on Docker Desktop using an isolated project name and a local, ignored `.env` file. The verified endpoints were `http://127.0.0.1:8010` (API) and `http://127.0.0.1:3010` (frontend).

- PostgreSQL 16, the FastAPI service, and nginx frontend all reached healthy/running status.
- `/health` reported `database: READY` and `data_mode: FIELD`.
- Chrome loaded the Docker-served frontend, selected a registered verification well, built a measured-data snapshot, and displayed its ingested oil-rate measurement without browser page errors.
- A versioned physical configuration and CSS thermal physics run were saved. The run reported `PARTIAL`; its thermal estimate was explicitly labeled `NOT_VALIDATED_ON_HELD_OUT_FIELD_DATA`.
- The API container was restarted. The registered well and all eight measurements remained retrievable. The saved physics run was also retrieved and inspected in the frontend after a page reload.
- Stopping only this Compose project's PostgreSQL container caused `/health` to return HTTP 503; starting it again restored `database: READY` and retained the measurements.
- Invalid measurement input returned HTTP 422, an unknown well returned HTTP 404, and the synthetic production forecast in field mode returned HTTP 503 as designed.
- Existing Python unittest suite: 58 passed. Existing Playwright suite: 6 passed. Both were run separately from the Docker field-mode browser journey.

This is local integration evidence only. It does not establish scientific calibration, held-out field accuracy, operational suitability, security review, or production readiness. Forecasting and optimization that require synthetic development profiles are unavailable in field mode by design.

## Prerequisites

- Start Docker Desktop and confirm its Linux engine is running with `docker info`.
- From the repository root, create `.env` from `.env.example` if needed. Set `POSTGRES_DB`, `POSTGRES_USER`, and a long URL-safe `POSTGRES_PASSWORD`. Keep `.env` private; it is ignored by Git.
- The first image build needs access to container and package registries.
- Choose free local API/frontend ports in `.env`. The verification run used 8010 and 3010 because the default ports were already in use. The PostgreSQL port is not published to the host.

Validate Compose without starting containers:

```powershell
docker compose --env-file .env -p petrotwin-verify-20261123 config --quiet
```

Build and start the isolated project:

```powershell
docker compose --env-file .env -p petrotwin-verify-20261123 up -d --build --wait --wait-timeout 180
docker compose --env-file .env -p petrotwin-verify-20261123 ps
Invoke-RestMethod http://127.0.0.1:8010/health
Invoke-WebRequest http://127.0.0.1:3010/
```

The verified project uses the named volume `petrotwin-verify-20261123_petrotwin_runtime_data`. Reuse the same project name to reconnect to that database. A different Compose project name creates a different volume and database.

## Field-mode verification path

Field mode has no seeded demo wells and does not produce synthetic forecasts. Register a test well, ingest timezone-aware measured records for that well, and create snapshots with the `/api/v1/wells` and `/api/v1/measurements` APIs. The verification fixture used `VERIFY-20261123-01`; eight measurements, including oil rate, injection pressure, temperature, bottomhole pressure, steam mass, soak time, SPM, and stroke length, were retained in the isolated test database.

Build the snapshot from the selected well's measured state, save an explicitly sourced physical configuration, and execute only models whose required measured inputs and configuration are eligible. Results expose their inputs, provenance, assumptions, validation status, and unavailable models. A computed estimate is not a field-validated prediction.

To verify persistence, restart only the API service and query the same well's measurements and saved physics-run history again:

```powershell
docker compose --env-file .env -p petrotwin-verify-20261123 restart ml-service
Invoke-RestMethod http://127.0.0.1:8010/health
Invoke-RestMethod 'http://127.0.0.1:8010/api/v1/wells/VERIFY-20261123-01/measurements?days=3650'
Invoke-RestMethod 'http://127.0.0.1:8010/api/v1/wells/VERIFY-20261123-01/physics-runs'
```

## Stop safely

```powershell
docker compose --env-file .env -p petrotwin-verify-20261123 stop
```

Stopping retains the named PostgreSQL volume. Do not run `down -v` or `docker volume prune` when data must be preserved. Do not stop or remove other Compose projects, containers, or volumes as part of this verification.
