# CI pipeline

The GitHub Actions workflow at `.github/workflows/ci-cd.yml` runs on pushes and pull requests targeting `main`, plus manual dispatch. It does **not** deploy the application.

## Jobs

1. **Frontend:** Node 20, `npm ci`, TypeScript/Vite production build, and upload of the generated frontend bundle.
2. **Python API/physics/MCP:** Python 3.12, install the repository-root `requirements.txt` (FastAPI plus pinned MCP SDK), run `python scripts/test_all.py`, and use FastAPI `TestClient` to verify `/health`.
3. **Container build validation:** build the FastAPI and frontend Dockerfiles after the first two jobs pass.

Spring Boot remains in the repository as dormant legacy source and is not a required job in the canonical application workflow. No PostgreSQL service is provisioned in this workflow; API tests use an isolated temporary SQLite file. Docker Compose integration and browser end-to-end journeys are not currently run in CI.

Deployment to Render/Vercel is separate and must be configured and verified independently. A green workflow only establishes the checks above; it does not mean deployment succeeded or that model outputs are field validated.
