# Blue Notes Backend Service

Backend REST service for team note-taking, built with Django, Django REST Framework, and PostgreSQL.

---

## 🚀 Quick Start (Local Docker Setup)

The project is fully dockerized for local development and testing using standard `compose/local/` container configurations.

> **Note on `.env.local`**:
> `.env.local` is intentionally committed to the repository with standard local development credentials to provide a frictionless, clone-and-run experience for reviewers. In production environments, credentials are provided via external environment variable injectors or secret managers.

### 1. Build and Run the Services

```bash
docker compose -f local.yml up --build
```
*(or simply `docker compose up --build`)*

The service will run migrations automatically on boot and start at [http://localhost:8000](http://localhost:8000).

### 2. Run Tests & Linter

```bash
# Run pytest suite
docker compose -f local.yml exec django pytest

# Run Ruff linter & format check
docker compose -f local.yml exec django ruff check .
docker compose -f local.yml exec django ruff format --check .
```

### 3. Health Check

Verify the service is responding:
```bash
curl http://localhost:8000/health/
```
Expected response:
```json
{"status": "ok", "service": "blue_notes"}
```
