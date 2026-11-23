# Cloud deployment status

Cloud deployment is not a verified project capability. Older Render/Vercel instructions in this repository assumed live services, production persistence, and a `LIVE STREAM` indicator; those assumptions do not match the current code and have been removed.

The reproducible, supported development target is local React + FastAPI + SQLite, or Docker Compose React + FastAPI + PostgreSQL. See [dev-setup.md](dev-setup.md).

Before a cloud deployment is considered, it needs at least:

- A managed persistent database and tested backups/migrations.
- HTTPS, authentication, authorization, secret management, restrictive CORS, and rate limiting.
- Explicit simulation/measurement provenance and a supported data contract.
- A deployment-specific `VITE_API_URL`, model artifact/version compatibility, health checks, and verified browser-to-API smoke tests.
- A deployment workflow that actually builds, deploys, and checks the named services. The current GitHub workflow builds artifacts only and does not deploy.

Do not connect operational field systems or use synthetic recommendations as setpoints. This repository has no validated field-data adapter or dispatch integration.
