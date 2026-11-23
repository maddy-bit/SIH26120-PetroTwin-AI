# 🛢️ PETRO-TWIN AI: Well-to-Surface Digital Twin for CSS + SRP Joint Optimization

[![SIH 2026](https://img.shields.io/badge/SIH-2026-orange.svg?style=flat-square)](https://sih.gov.in)
[![Problem Statement](https://img.shields.io/badge/Problem%20Statement-SIH26120-blue.svg?style=flat-square)](https://sih.gov.in)
[![Target Operator](https://img.shields.io/badge/Operator-Oil%20India%20Limited-darkred.svg?style=flat-square)](https://www.oil-india.com)
[![Target Field](https://img.shields.io/badge/Field-Baghewala%20Heavy%20Oil%20(Rajasthan)-green.svg?style=flat-square)]()
[![React 19](https://img.shields.io/badge/Frontend-React%2019%20%7C%20Vite%20%7C%20Tailwind%20%7C%20Recharts-61dafb.svg?style=flat-square)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/Backend%20%2B%20Physics%20%2B%20ML-FastAPI%20%7C%20Python%203.12-009688.svg?style=flat-square)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/Database-TimescaleDB%20%7C%20PostgreSQL%2016-336791.svg?style=flat-square)](https://www.postgresql.org)
[![Docker](https://img.shields.io/badge/Containers-Docker%20Compose-2496ed.svg?style=flat-square)](https://www.docker.com)
[![CI/CD Pipeline](https://github.com/maddy-bit/SIH26120-PetroTwin-AI/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/maddy-bit/SIH26120-PetroTwin-AI/actions)

---

## 📌 Project Scenario Assumptions (Not Validated Field Data)

* **Organization:** Oil India Limited (OIL)
* **Category:** Software
* **Theme:** Smart Automation / Oil & Gas Digitalization
* **Target Asset:** Baghewala Field Heavy Oil Wells, Jodhpur Sandstone Formation, Bikaner-Nagaur Basin, Rajasthan, India
* **Crude Characteristics:** Extra-heavy dead crude ($17^\circ\text{–}19^\circ\text{ API}$), reservoir viscosity $> 4,000\text{ cP}$ at native temperature ($47^\circ\text{C}$), high asphaltic/wax content.

### The Physics Dilemma
At Baghewala Field, primary cold production is virtually zero due to immense fluid friction. Operators inject high-pressure supercritical steam ($280^\circ\text{–}310^\circ\text{C}$, $1,200\text{–}1,800\text{ tonnes}$) during **Cyclic Steam Stimulation (CSS)** to lower oil viscosity from $4,200\text{ cP}$ down to $\sim 14.5\text{ cP}$.

As the well is put on **Sucker Rod Pump (SRP)** production:
1. Over a 90–120 day production window, **heat naturally dissipates** into surrounding underburden/overburden formations ($T_{\text{res}} \downarrow 47^\circ\text{C}$).
2. Viscosity rebounds exponentially back toward $> 1,000\text{ cP}$.
3. When surface operators maintain a constant pumping speed (e.g. 6 SPM), the downhole rod string **cannot sink under gravity** through the viscous fluid column during the downstroke.
4. This induces **Rod Floating**, causing slack bridle cables, severe shock loading upon re-engagement ($5,000\text{ m/s}$ acoustic impact stress waves), mechanical fatigue, and **catastrophic rod parted failures**.

---

## 💡 Solution Overview: PETRO-TWIN AI

**PETRO-TWIN AI** is a synthetic decision-support prototype exploring how post-CSS thermal decline and viscosity changes relate to SRP loading, failure-risk heuristics, and joint steam/pump trade-offs. It does not eliminate failures, use field telemetry, or prescribe operational setpoints.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    REACT CONTROL ROOM + AUTH GATE                        │
│  Field Data • CSS/SRP Scenario Lab • Coupled Physics • Pareto Review     │
│  Evidence Copilot • Model Registry • Source/Quality Status              │
└───────────────────────────────────┬──────────────────────────────────────┘
                                    │ HTTP REST / WebSocket
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                         FASTAPI APPLICATION                              │
│  Authentication/RBAC • Request Validation • Ingestion • Orchestration   │
├──────────────────────────────────────────────────────────────────────────┤
│ Physics/CSS→Cooling→Viscosity→SRP • Calibration • Field ML Training      │
│ Finite-Grid Optimizer • Read-only MCP-backed Industrial Agent            │
└───────────────────────────────────┬──────────────────────────────────────┘
                                    │ Repository + model artifacts
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    POSTGRESQL 16 / SQLITE                                │
│  Measurements & Provenance • Calibration • Users/Audit • Agent Runs     │
│  Model Registry • SHA-256-verified Field Model Artifacts                 │
└──────────────────────────────────────────────────────────────────────────┘

Agent path: FastAPI AgentRuntime → MCP stdio client → read-only PETRO-TWIN MCP tools
           → shared repository evidence → configured OpenAI-compatible LLM
```

---

## 🔬 Core Physics Equations & Mathematical Models

### 1. Viscosity-Temperature Inversion (ASTM D341 / Walther Equation)
$$\log_{10}(\log_{10}(\nu + 0.7)) = A - B \cdot \log_{10}(T_K)$$
* $47^\circ\text{C}$ (Native Reservoir): $\mu = 4,200\text{ cP}$
* $100^\circ\text{C}$ (Moderate Heat): $\mu = 145\text{ cP}$
* $200^\circ\text{C}$ (Peak Steam Zone): $\mu = 14.5\text{ cP}$

### 2. Marx-Langenheim Thermal Plume Dissipation
$$T_{\text{res}}(t) = T_{\text{native}} + (T_{\text{peak}} - T_{\text{native}}) \cdot \exp\left( -\left[ \lambda_{\text{cond}} + \lambda_{\text{conv}} \cdot q_L(t) \right] \cdot t \right)$$
* $\lambda_{\text{cond}}$: Conductive earth heat loss coefficient ($\sim 0.018\text{ day}^{-1}$)
* $\lambda_{\text{conv}}$: Convective thermal transport with produced effluent ($\sim 0.00015\text{ (bbl/d)}^{-1}\cdot\text{day}^{-1}$)

### 3. Rod Floating Criterion & Couette Shear Sinking Drag
Couette annular viscous drag force on the sucker rod downstroke:
$$F_{\text{drag}} = \frac{2 \pi \mu L v_r}{\ln(r_t / r_r)}$$
Terminal sinking velocity of the sinker bar / rod string:
$$v_{\text{terminal}} = \frac{W_{\text{rod, buoyant}}}{C_{\text{drag}}}$$
**Physical Rod Floating Condition:**
$$\text{If } v_{\text{max, horsehead}} \ge 0.80 \cdot v_{\text{terminal}} \implies \textbf{ROD FLOATING DETECTED}$$

---

## Evaluation status

The checked-in training report evaluates on synthetic records generated from the same simulator and rule labels used by the project. It is not a field benchmark or independent validation. Current forecast ranges are heuristics, and the optimizer performs a finite grid search. Demo outputs are not measured performance or operational prescriptions.

---

## 🚀 Quickstart Guide

For the reproducible Windows setup, start/stop commands, health checks, and troubleshooting, see [docs/dev-setup.md](docs/dev-setup.md).

### Prerequisites
* **Python 3.11+**
* **Node.js 18+** & `npm`
* **Java 21** & `mvn` *(Optional for Docker mode)*
* **Docker & Docker Compose** *(Optional for Full Stack mode)*

### Option A: Instant Local Development (Recommended)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/maddy-bit/SIH26120-PetroTwin-AI.git
   cd SIH26120-PetroTwin-AI
   ```

2. **Install dependencies and run all automated tests:**
   ```bash
   pip install -r requirements.txt
   python scripts/test_all.py
   ```
   The root requirements file installs both the FastAPI service dependencies and the pinned MCP SDK.

3. **Train / Re-train All Machine Learning Models:**
   ```bash
   python scripts/train_models.py
   ```
   Optional: regenerates synthetic model artifacts in `ml_service/saved_models/`. This overwrites those tracked artifacts; use only when intentionally retraining.

4. **One-Command Local Launcher (Windows PowerShell):**
   ```powershell
   .\scripts\run_all_local.ps1
   ```

5. **Or Run Services Manually:**
   * **Terminal 1 (Physics & ML Service):**
     ```bash
     python -m uvicorn ml_service.main:app --host 127.0.0.1 --port 8000 --reload
     ```
   * **Terminal 2 (React Control Room Frontend):**
     ```bash
     cd frontend
     npm ci
     npm run dev
     ```
   * **Open Browser:** `http://localhost:5173` (or `http://localhost:3000`)

---

### Option B: Full Stack Docker Compose

```powershell
Copy-Item .env.example .env
# Replace POSTGRES_PASSWORD in .env with a strong URL-safe local password.
docker compose up --build
```

**Service Endpoints:**
* **Frontend Web Dashboard:** [http://localhost:3000](http://localhost:3000)
* **Canonical application API:** FastAPI at [http://localhost:8000](http://localhost:8000)
* Spring Boot is legacy source only, outside the frontend request path.
* **FastAPI API docs:** [http://localhost:8000/docs](http://localhost:8000/docs) in local development; hidden in required-auth mode.
* PostgreSQL is internal to the Compose network; no host port is published.

For local development/demonstration, the default Compose profile runs with authentication disabled and must remain bound to a trusted local machine. To run the authenticated production-oriented profile, configure a secret and use the override:

```powershell
$env:PETROTWIN_JWT_SECRET = (python -c "import secrets; print(secrets.token_urlsafe(48))")
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d --build --wait
docker compose -f docker-compose.yml -f docker-compose.production.yml run --rm ml-service python scripts/manage_users.py create --username <admin-username> --role admin
```

The first administrator is created interactively; there is no default password. Configure TLS, rate limiting, CSP, managed secrets, backups and production monitoring before public exposure.

---

## 📂 Repository Directory Layout

```text
SIH26120-PetroTwin-AI/
├── agent/                         # Agentic AI Copilot & Deterministic Tool Supervisor
│   ├── agent_supervisor.py         # Legacy deterministic simulation supervisor
│   └── agent_runtime.py             # Read-only MCP-backed LLM investigation runtime
├── mcp_server/                      # Official MCP SDK server: read-only tools/resources/prompts
│   ├── server.py
│   └── requirements.txt
├── backend/                       # Dormant Spring Boot source and legacy migrations
│   └── springboot/
│       ├── pom.xml
│       └── src/main/
│           ├── java/com/petrotwin/
│           └── resources/
│               ├── application.yml
│               └── db/migration/  # Flyway V1 schema & V2 seed migrations
├── config/                        # Explicit model defaults and assumptions; not field calibration
│   └── physics.yaml
├── data/                          # Data source governance & registry
│   └── sources/
│       └── dataset_sources.yaml
├── docker/                        # Multi-stage production container Dockerfiles
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   ├── Dockerfile.ml-service
│   └── nginx.conf
├── docs/                          # Comprehensive SIH 18-part technical dossier
│   ├── 01-problem-understanding.md
│   ├── 02-system-architecture.md
│   ├── 03-petroleum-domain.md
│   ├── 04-css-model.md
│   ├── 05-srp-model.md
│   ├── 06-digital-twin.md
│   ├── 07-ml-models.md
│   ├── 08-optimization.md
│   ├── 09-agentic-ai.md
│   ├── 10-data.md
│   ├── 11-api.md
│   ├── 12-database.md
│   ├── 13-deployment.md
│   ├── 14-testing.md
│   ├── 15-benchmarking.md
│   ├── 16-limitations.md
│   ├── 17-demo-script.md
│   ├── 18-jury-defense.md
│   └── competitive-analysis.md
├── frontend/                      # React 19 + TypeScript + Vite + Tailwind Control Room
│   ├── package.json
│   ├── src/
│   │   ├── components/            # AuthGate, Field Models, Copilot, Dyno/Pareto/Scenario UI
│   │   ├── services/api.ts        # FastAPI client with explicit error states
│   │   ├── types/petro.ts         # Strictly typed engineering domain interfaces
│   │   ├── App.tsx
│   │   └── index.css
│   └── vite.config.ts
├── ml_service/                    # Python FastAPI Physics & ML Microservice
│   ├── main.py                    # REST and WebSocket endpoints
│   ├── config.py                  # Runtime, database, auth and agent configuration
│   ├── models/                    # Forecaster, Failure Predictor, Anomaly Detector
│   ├── optimizer/                 # Finite grid search and nondominated filtering
│   ├── services/                  # Ingestion, calibration, measured-data ML training
│   ├── auth.py                    # Password, JWT session and RBAC service
│   ├── persistence.py             # SQLite/PostgreSQL repository and migrations
│   ├── simulator/                 # Synthetic telemetry for simulation mode
│   └── requirements.txt
├── physics/                       # First-principles petroleum physics package
│   ├── __init__.py
│   ├── thermal_model.py           # Marx-Langenheim heat balance
│   ├── viscosity_model.py         # ASTM D341 Walther viscosity equation
│   ├── wellbore_model.py          # 1D discretized wellbore hydraulics
│   ├── srp_model.py               # Approximate SRP mechanics and dyno cards
│   └── coupled_css_srp_model.py   # Shared CSS → cooling → viscosity → SRP simulation chain
├── scripts/                       # Automated test, run and account-provisioning scripts
│   ├── run_all_local.ps1          # Test, then start local services and check health
│   ├── start-dev.ps1              # Start FastAPI and Vite
│   ├── stop-dev.ps1               # Stop the recorded development processes
│   ├── health-check.ps1           # Check FastAPI and Vite
│   ├── seed_database.py          # Telemetry and well state seeder
│   ├── test_all.py                # Unified test runner
│   └── manage_users.py             # Interactive first-admin/user provisioning
├── tests/                         # Physics, ML, auth, agent and integration test suites
│   ├── test_physics.py
│   └── test_ml_service.py
├── docker-compose.yml             # Container orchestration
└── README.md                      # Master technical documentation
```

---

## ☁️ Cloud Deployment

Optional deployment configuration exists for Render/Vercel, but is not part of the verified local application workflow.

> 📖 **Full Step-by-Step Instructions:** See [docs/18-cloud-deployment-guide.md](docs/18-cloud-deployment-guide.md) for full configuration details.

### Quick Deployment Summary:
1. **Render (Backend):**
   * Repo: `maddy-bit/SIH26120-PetroTwin-AI`
   * Build Command: `pip install -r requirements.txt` (run from repository root; includes MCP SDK)
   * Start Command: `uvicorn ml_service.main:app --host 0.0.0.0 --port $PORT`
2. **Vercel (Frontend):**
   * Repo: `maddy-bit/SIH26120-PetroTwin-AI`
   * Root Directory: `frontend`
   * Environment Variable: `VITE_API_URL=https://<your-render-service>.onrender.com`

These are configuration examples only; this deployment path has not been validated. See [deployment status and prerequisites](docs/18-cloud-deployment-guide.md).

---

## 🔄 Automated CI/CD Pipeline (GitHub Actions)

Every pull request and push to `main` executes a multi-stage validation pipeline:
1. **Frontend CI:** Node 20 + TypeScript compilation (`tsc -b`) + Vite production build (`dist/` artifact archive).
2. **ML & Physics CI:** Python 3.12 + test suite + FastAPI health check validation (`TestClient`).
3. **Container validation:** FastAPI and frontend Dockerfile builds.
4. Deployment is separate from this CI workflow and must be independently configured and verified.

> 📖 **Full Pipeline Documentation:** See [docs/19-ci-cd-pipeline.md](docs/19-ci-cd-pipeline.md).

---

## 🌐 Key REST API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |

| `GET` | `/health` | Liveness, database and auth-mode status |
| `GET` | `/api/wells` | Registered well list; demo wells appear only in simulation mode |
| `POST` | `/api/v1/measurements/csv` | Validated field-measurement CSV ingestion with quality/provenance |
| `GET` | `/api/v1/wells/{well_id}/data-quality` | Data-quality and availability summary |
| `POST` | `/simulate/scenario` | Simulation-only CSS–SRP coupled scenario and intermediate physics trace |
| `POST` | `/optimize/joint` | Finite-grid candidate comparison; decision-support only |
| `GET` | `/api/v1/agent/status` | Read-only MCP agent/provider readiness |
| `POST` | `/api/v1/agent/investigate` | Evidence-grounded LLM investigation (requires configured model provider) |
| `GET` | `/api/v1/agent/runs` | Persisted agent responses and read-only tool traces |
| `POST` | `/api/v1/auth/login` | Username/password sign-in |
| `GET` | `/api/v1/auth/me` | Current authenticated session |
| `POST` | `/api/v1/auth/logout` | Revoke current session |
| `GET/POST/PATCH` | `/api/v1/auth/users` | Admin user/role management |
| `POST` | `/api/v1/models/production/train` | Train measured-data candidate (field mode only) |
| `GET` | `/api/v1/models/production` | Model registry for the selected well |
| `POST` | `/api/v1/models/{model_id}/promote` | Admin-only artifact verification and promotion |
| `GET` | `/api/v1/models/production/predict` | Inference using a promoted field model and fresh VALID inputs |

Protected endpoints require a bearer token when `PETROTWIN_AUTH_MODE=required`. Synthetic prediction and telemetry routes remain simulation-only; read [docs/16-limitations.md](docs/16-limitations.md) before interpreting model or optimization outputs.

---

## 🎯 SIH Jury 5-Minute Guided Demo Walkthrough

When presenting to evaluators, click the **"5-MIN JURY DEMO"** button on the top navbar:
1. **Minute 1: The Heavy Oil Dilemma (`/dashboard`)**
   * Select a synthetic demo well and inspect its configured state and simulation disclaimer.
2. **Minute 2: Simulated Telemetry & Dyno Card (`/live-ops`)**
   * Inspect the generated telemetry and synthetic dynamometer card.
3. **Minute 3: 180-Day Digital Twin Time Machine (`/digital-twin`)**
   * Select a cycle day and inspect the simplified temperature and viscosity projection.
4. **Minute 4: Rod Floating Risk & Explainable AI (`/failures`)**
   * Inspect modeled risk estimates and the synthetic operating state.
   * Inspect the heuristic risk contribution display; it is not SHAP attribution.
5. **Minute 5: Pareto Optimization & Agentic Copilot (`/pareto`)**
   * Run the finite-grid search on demand and review its synthetic candidate trade-offs; no setpoint is dispatched.
   * Open the Evidence Copilot to retrieve registered measurements and operational records through read-only MCP tools. Configure an OpenAI-compatible provider before demonstrating LLM synthesis; otherwise the agent deliberately reports that it is unavailable.

---

## 🛡️ Scientific Data Honesty & Source Attribution
Current demo telemetry and ML training/evaluation records are synthetic. The repository has no field-data ingestion adapter or validated field dataset. Physics equations are simplified project models and need independent engineering review before operational use.

---

## 👥 Authors & Team
* **Project:** PETRO-TWIN AI
* **Smart India Hackathon 2026** — Problem Statement SIH26120
* **Repository Owner:** [maddy-bit](https://github.com/maddy-bit)
* **Contact:** anmoltrived44@gmail.com
