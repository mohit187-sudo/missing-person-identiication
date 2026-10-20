# Missing Person Identification System

A secure, full-stack, AI-assisted platform that helps **authorized investigators and rescue teams**
identify missing persons through facial similarity search, authorized CCTV footage analysis, and a
human-verification workflow.

> **⚠️ Responsible use — read first**
> - Similarity scores are **technical measurements between facial embeddings**. They are **NOT**
>   the probability that two images show the same person.
> - The system **never** automatically identifies anyone, never changes case status on its own,
>   and never triggers law-enforcement action from an AI result.
> - Every candidate requires **human verification and independent corroboration**.
> - Use only for **lawful** missing-person investigations with appropriate authorization.
> - Demographic characteristics are never used to infer identity.
> - Demo data is synthetic, clearly labelled, and never mixed with real case results.

---

## Features

| Area | Implemented |
|---|---|
| **Auth** | Admin-managed accounts (public sign-up disabled), Argon2id hashing, short-lived JWT access tokens, rotating refresh tokens with reuse detection, login rate limiting + lockout, password change/reset workflow, account deactivation |
| **Roles** | Administrator · Authorized investigator · Rescue-team user — enforced on **every** backend endpoint (frontend checks are UX only) |
| **Case management** | Server-generated case IDs (`MPI-YYYY-XXXXXX`), full registration form with consent/legal basis, create/view/update/archive, search + filters + pagination, status history, duplicate-case warnings, photo uploads with validation, soft deletion |
| **AI matching** | Pluggable face backend (OpenCV YuNet detector + SFace embeddings, Apache-2.0), image-quality gates (blur/size/brightness), L2-normalised 128-d embeddings, cosine similarity, ranked candidates with scores/thresholds/model provenance, configurable thresholds, clear setup error + non-biometric demo mode when weights are missing — **never** fake scores |
| **CCTV analysis** | Authorized-footage upload with legal confirmation, codec/size/duration probing, frame sampling, face detection with quality filtering, comparison against authorized case records, processing progress + cancellation, CSV/PDF review reports (video ID, timestamp, candidate case, score, model) |
| **Review workflow** | Ranked potential matches, review history, decisions (confirm for investigation / reject / manual review), confirmations require documented notes, case status never changes automatically |
| **Privacy & security** | Private storage (never publicly served), security headers, CORS allowlist, upload validation (type/size/decode/hash), malware-scan integration point, rate limiting, audit logs, configurable retention + secure-deletion pass, correction/deletion request workflow, biometric access restricted |
| **Notifications** | In-app alerts (job completion, match reviews) with minimal content; optional SMTP email (disabled by default) |
| **Reports** | CSV + PDF case reports, video review reports, activity summary, dashboard stats from live DB records |
| **Database** | 17 normalized tables, UUID PKs, FKs/constraints/indexes, Alembic migrations, PostgreSQL primary (Docker Compose) + SQLite fallback, optional pgvector (see `docs/PGVECTOR.md`) |
| **Demo mode** | `scripts/seed_demo.py` seeds synthetic cases clearly flagged `is_demo` with “SYNTHETIC DEMO DATA” images |

### Clearly identified items needing external infrastructure

| Item | Status |
|---|---|
| Face model weights (~38 MB) | **Not committed to git** — run `python scripts/download_models.py` (free, Apache-2.0, from opencv/opencv_zoo) |
| Email alerts | Optional — configure SMTP in `.env`; otherwise the app logs and relies on in-app notifications |
| Cloud object storage (S3-compatible) | Optional — local protected storage is the default; `OBJECT_STORAGE_*` settings are provided as the integration point |
| Malware scanning | Integration point provided (`scan_for_malware` in `backend/app/services/storage.py`); wire in ClamAV or a cloud scanner |
| pgvector vector index | Optional — see `docs/PGVECTOR.md` |
| Horizontal scaling of jobs/rate limits | In-process today (threads + in-memory limiter); swap points documented in code for Celery/Redis |

---

## Tech stack

- **Frontend:** React 18 + Vite + TypeScript, Tailwind CSS, React Hook Form + Zod, Recharts, Lucide icons, Vitest + React Testing Library
- **Backend:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, JWT (PyJWT), Argon2id
- **Database:** PostgreSQL 16 (pgvector image) via Docker Compose; SQLite fallback for quick local demo
- **AI:** OpenCV (YuNet face detection + SFace embeddings), Pillow, numpy — fully local, no paid API
- **Video:** OpenCV pipeline with background job runner

---

## Project structure

```
missing-person-identification-system/
├── frontend/                 # React + Vite + TS dashboard
│   └── src/{components,pages,hooks,services,types}
├── backend/
│   ├── app/
│   │   ├── api/              # versioned REST routes (/api/v1/...)
│   │   ├── core/             # config, security, structured errors
│   │   ├── db/               # engine, session, bootstrap
│   │   ├── models/           # SQLAlchemy ORM (17 tables)
│   │   ├── schemas/          # Pydantic request/response models
│   │   ├── services/         # audit, notifications, email, storage, PDF
│   │   ├── security/         # rate limiting
│   │   ├── ai/               # pluggable face backends + matching service
│   │   ├── video/            # CCTV processing pipeline
│   │   └── tasks/            # background job runner
│   ├── alembic/              # migrations
│   └── models/               # ONNX weights live here (git-ignored)
├── tests/{backend,frontend}  # pytest + Vitest suites
├── scripts/                  # download_models, seed_demo, create_admin
├── storage/                  # private uploads (git-ignored)
├── alembic.ini
├── docker-compose.yml
├── .env.example
└── requirements.txt
```

---

## Quick start (VS Code, Windows-friendly)

### 1. Prerequisites

| Tool | Version | Windows notes |
|---|---|---|
| Python | 3.11+ | `py -3.11 --version` — install from python.org, tick “Add to PATH” |
| Node.js | 18+ (20 LTS recommended) | from nodejs.org |
| Docker Desktop | latest | for PostgreSQL (`docker compose up -d db`) — optional if you use the SQLite fallback |
| Git | latest | |

Verify in **VS Code terminal** (Ctrl+`):

```powershell
python --version      # or: py -3.11 --version
node --version
docker --version
```

### 2. Clone & open

```powershell
git clone <your-repo-url>
cd missing-person-identiication
code .
```

### 3. Environment variables

```powershell
copy .env.example .env
```

Generate a secure JWT secret (PowerShell):

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Paste the value into `.env` as `JWT_SECRET_KEY=` (in development it is optional — an ephemeral
secret with a loud warning is generated; **required in production**). No other secrets are needed
for the local demo. `DEMO_MODE=true` enables clearly-labelled synthetic data.

### 4. Python virtual environment

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
# If script execution is blocked:  Set-ExecutionPolicy -Scope Process RemoteSigned
```

**Windows (CMD):** `.venv\Scripts\activate.bat`
**macOS / Linux:** `source .venv/bin/activate`

### 5. Backend dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 6. Database

**Option A — PostgreSQL via Docker (recommended):**

```powershell
docker compose up -d db
```

Set in `.env`:

```
DATABASE_URL=postgresql+psycopg://mpis:mpis@localhost:5432/mpis
```

**Option B — SQLite fallback (no Docker):** leave `DATABASE_URL=sqlite:///./storage/dev.db` in `.env`.

### 7. Database migrations

```powershell
alembic upgrade head
```

(For local demo the backend also auto-creates the schema and baseline roles on first start.)

### 8. AI model weights (for real facial matching)

```powershell
python scripts/download_models.py
```

Downloads YuNet + SFace ONNX weights (~38 MB, **Apache-2.0**, official opencv/opencv_zoo) into
`backend/models/`. Verify at `GET /api/health/ready` → `ai_model.ok=true`.
Without weights the app runs in **non-biometric demo mode**: matching endpoints return a structured
setup error (503 `ai_model_unavailable`) — the system **never** fabricates scores.

### 9. Demo data seeding (optional, clearly labelled)

```powershell
python scripts/seed_demo.py
```

Creates synthetic cases (`DEMO-2026-xxxx`, flagged `is_demo`) with “SYNTHETIC DEMO DATA — NOT A
REAL PERSON” images, plus demo accounts (printed at the end).

### 10. First administrator

```powershell
python scripts/create_admin.py --email admin@example.com --password "REPLACE-with-a-strong-pass"
```

(Or run it without arguments for hidden interactive prompts.)

### 11. Run the backend

```powershell
uvicorn backend.app.main:app --reload --port 8000
```

### 12. Run the frontend (second terminal)

```powershell
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** — the dev server proxies `/api` to the backend (no CORS issues,
no hardcoded URLs).

### 13. Swagger API documentation

With the backend running open: **http://localhost:8000/api/docs** (ReDoc at `/api/redoc`).

### 14. Tests

```powershell
# Backend (pytest + coverage)
pytest

# Frontend (Vitest + Testing Library)
cd frontend
npm test

# TypeScript check
npm run lint
```

### 15. Troubleshooting

| Problem | Fix |
|---|---|
| `alembic: command not found` | Activate the venv; `pip install alembic` |
| `no such table: users` | Run `alembic upgrade head` (or just start the backend once — it bootstraps the schema) |
| `AI model unavailable` / 503 on `/matching/search` | Run `python scripts/download_models.py`, confirm `AI_MODEL_PATH=./backend/models`, restart backend, check `/api/health/ready` |
| `Cannot open video / corrupt file` | The file is not a readable container (codec missing or truncated). Re-encode to H.264 MP4 with ffmpeg/HandBrake |
| `MJPG writer unavailable` in video tests | Some minimal OpenCV builds lack codecs; the tests skip gracefully |
| Windows: `Activate.ps1 cannot be loaded` | `Set-ExecutionPolicy -Scope Process RemoteSigned` then retry |
| Windows: `opencv` install fails | Install the wheel: `pip install opencv-python-headless` (no compiler needed) |
| Port 8000/5173 busy | `uvicorn ... --port 8001` / `npm run dev -- --port 5174` |
| Login 429 rate limited | Wait a minute (5 attempts/min) or set `RATE_LIMIT_ENABLED=false` for local dev |
| `email-validator` rejects an address | Use a normal domain (e.g. `example.com`); special-use domains like `test.local` are refused |
| Docker not available | Use the SQLite fallback (step 6, Option B) |

---

## API overview (all under `/api/v1`, Swagger for the full contract)

**Auth:** `POST /auth/login` · `POST /auth/refresh` · `POST /auth/logout` · `GET /auth/me` ·
`POST /auth/change-password` · `POST /auth/request-password-reset` · `POST /auth/confirm-password-reset`

**Cases:** `POST /cases` · `GET /cases` · `GET /cases/{id}` · `PATCH /cases/{id}` · `DELETE /cases/{id}` ·
`GET /cases/{id}/duplicates` · `POST /cases/{id}/photos` · `GET /cases/{id}/photos/{pid}/file` · `DELETE /cases/{id}/photos/{pid}`

**AI matching:** `POST /matching/search` · `GET /matching/jobs/{job_id}` · `GET /matching/ai-status` ·
`GET /matches` · `GET /matches/{id}` · `POST /matches/{id}/review` · `GET /matches/{id}/photo`

**Video evidence:** `POST /videos` · `GET /videos` · `GET /videos/{id}` · `POST /videos/{id}/process` ·
`GET /videos/{id}/status` · `GET /videos/{id}/report?format=json|csv|pdf` · `POST /videos/jobs/{id}/cancel` ·
`GET /videos/{id}/faces`

**Administration:** `GET/POST /admin/users` · `PATCH /admin/users/{id}` · `GET /admin/audit-logs`

**Notifications:** `GET /notifications` · `GET /notifications/unread-count` · `POST /notifications/{id}/read` · `POST /notifications/read-all`

**Reports:** `GET /stats/overview` · `GET /reports/cases?format=csv|pdf` · `GET /reports/activity-summary`

**Privacy:** `GET/PUT /privacy/retention-policies[...]` · `POST /privacy/run-retention` ·
`POST/GET/PATCH /privacy/correction-requests[...]`

**Health:** `GET /api/health` · `GET /api/health/ready`

---

## Security & privacy design

- **AuthN/AuthZ:** Argon2id passwords; 15-min JWT access tokens; opaque rotating refresh tokens
  (SHA-256 hashed at rest, family reuse detection revokes all sessions); role checks in FastAPI
  dependencies on every protected route; account lockout after repeated failures.
- **CSRF:** tokens live in `localStorage` and travel as `Authorization: Bearer` headers (not
  cookies), so classic CSRF does not apply. If cookie auth is ever added, add double-submit CSRF
  tokens first (noted in `backend/app/main.py`).
- **Transport/headers:** security headers on every response (CSP, `X-Frame-Options: DENY`,
  nosniff, referrer policy), HSTS-ready; CORS allowlist without wildcards.
- **Uploads:** extension + MIME + Pillow decode verification, size limits, SHA-256 hashing,
  dedupe, private storage outside any web root, authenticated download endpoints only.
- **Biometric data:** embeddings restricted to administrator/investigator roles; stored with model
  provenance; deleted by the configurable retention pass (`POST /api/v1/privacy/run-retention`).
- **Audit:** every sensitive operation (logins, case CRUD, uploads, searches, reviews, admin
  changes) recorded in an append-only `audit_logs` table with actor, IP and detail.
- **Mistaken matches:** documented correction/deletion request flow
  (`POST /api/v1/privacy/correction-requests`) → admin review → audit-tracked resolution.

## Limitations (read before deploying)

- **Similarity ≠ identity.** Thresholds (default 0.55 cosine) **must** be tested on representative,
  lawfully obtained data before operational use. False positives and false negatives always exist.
- Performance varies with image quality, pose, lighting and occlusion; quality gates mitigate but
  do not eliminate poor inputs.
- The demo is a functional demonstration, not a validated forensic tool; no accuracy metrics are
  claimed or fabricated anywhere in the product.
- Video processing is single-node (threaded jobs). For production scale-out, move jobs to
  Celery/RQ and the rate limiter to Redis (integration seams are marked in code).
- Model licensing: OpenCV Zoo YuNet/SFace ONNX weights — Apache License 2.0 (see
  `backend/app/ai/opencv_sface.py` docstring). Verify license compatibility for your jurisdiction
  and use case (biometric data is regulated in many regions — e.g. GDPR, BIPA).

## License & attribution

Application code is provided for lawful missing-person identification use. The bundled AI engine
optionally uses [opencv/opencv_zoo](https://github.com/opencv/opencv_zoo) YuNet and SFace models
(Apache-2.0).
