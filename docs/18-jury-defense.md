# PETRO-TWIN AI — technical review notes

## Problem and hypothesis

The project investigates the interaction between Cyclic Steam Stimulation (CSS) and Sucker Rod Pumping (SRP) for heavy-oil production. CSS adds heat and can temporarily reduce oil viscosity. As the well cools, viscosity can rise and affect modeled SRP load, viscous drag and rod-floating risk. PETRO-TWIN aims to bring those variables into one evidence workflow rather than treating steam and pumping independently.

## Canonical architecture

React 19/TypeScript frontend → FastAPI/Python application → shared SQLite/PostgreSQL repository. FastAPI orchestrates validated field-data ingestion, physics calculations, calibration, measured-data model lifecycle, finite-grid candidate optimization, authentication/RBAC and the industrial investigation agent. The MCP server exposes read-only evidence tools to the agent. Spring Boot is legacy/dormant and not on the active frontend request path.

## What is implemented

- Validated manual CSV/JSON ingestion with units, source metadata, quality status and provenance.
- Persistent repository with SQLite local development and PostgreSQL 16 Compose migrations.
- Simplified thermal, viscosity and SRP calculations connected through an explicit simulation-only CSS → cooling → viscosity → SRP chain.
- Scientific calibration/validation framework; currently only the viscosity parameter adapter is enabled.
- Separate measured-data production ML trainer with time-safe features, purged chronological splits, persistence baseline, artifact hashing, model registry and explicit admin promotion.
- Finite-grid optimization and nondominated candidate review; not a validated global optimizer.
- scrypt/JWT session security, roles, admin user management and audit events.
- MCP-backed LLM investigation runtime with read-only tool allowlist, evidence trace persistence and explicit provider configuration.
- React Field Models view and login gate.

## What is demonstrated by software tests

Latest source verification: 80 Python tests passed, 7 Playwright E2E tests passed, frontend production build passed, Python compile checks passed, and git diff --check passed. An authenticated local Compose stack was previously built and verified with FastAPI/PostgreSQL healthy and schema migration version 9. The very latest backend changes to target-time purging and denial auditing passed the full Python suite; a final container rebuild is awaiting client approval.

## What is not proven

- No real Oil India/Baghewala time-series dataset is present. No field calibration, out-of-sample field validation or operator acceptance is claimed.
- The coupled physics composes simplified project equations; it does not solve a fully coupled multiphase reservoir, heat-transfer, wellbore or rod-string dynamics model.
- The ML trainer has not been run on real field measurements. A controlled fixture or chronological one-well holdout is not independent field validation.
- The live LLM provider is not configured on this machine. The agent runtime, stdio MCP path and read-only tool tests are implemented, but actual provider reasoning/quality has not been verified here.
- The official IBM AssetOpsBench benchmark has not been run; no AOB score is claimed.
- The optimizer is finite-grid search with limited coded constraints. It does not establish a global optimum or validate fracture pressure, gearbox torque or API allowable stress.
- No SCADA/historian/OPC-UA/MQTT integration or operating control/setpoint dispatch is configured.
- The local authenticated Compose profile is not a cloud production deployment or security certification. Local Nginx CSP/security headers and rate limits are implemented; public TLS/ingress, managed secrets, backup/recovery drills, monitoring, MFA/OIDC and independent security review remain.

## Evidence required for field acceptance

A permissioned and quality-reviewed dataset must include synchronized oil-rate, temperature, pressure, CSS cycle phase/injection/soak timing, SRP operating conditions, pump/rod geometry, dynamometer cards, event labels, units and source provenance. A petroleum/mechanical engineering owner must approve assumptions, calibration bounds, acceptance criteria and blind evaluation periods. Agent evaluation additionally requires frozen tasks, expected evidence, an evaluator and human correction rubric.

The application is a decision-support research prototype. It does not dispatch operating setpoints and is not validated for operational use.
