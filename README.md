# Blue Notes - Multi-Tenant Team Note-Taking Backend Service

Backend REST service for team note-taking, built with Django, Django REST Framework, and PostgreSQL.


---

## Design Choices and Tradeoffs


### 1. Multi-Tenancy via Row-Level Scoping with Composite Indexing vs. Separate Schemas/Databases
* **Decision:** I implemented multi-tenancy at the row level via `Team` and `TeamMembership` models, enforced through centralized QuerySet selectors (`apps/notes/selectors.py`) and granular RBAC permissions.
* **Why:** For small-to-medium teams, dedicated PostgreSQL schemas or separate databases introduce high operational overhead, complicated migration workflows, and connection pool fragmentation. Row-level scoping combined with composite database indexes (`[team, is_pinned, -created_at]`, `[author, team, deleted_at]`) provides sub-millisecond query performance, strict tenant isolation, and simple migrations.
* **Tradeoff:** Application logic must guarantee that all queries are scoped to the authenticated user's memberships. I mitigated the risk of cross-tenant data leaks by centralizing query construction in dedicated selectors rather than scattering raw `.filter()` calls across views.

### 2. Optimistic Concurrency Control (OCC) for Collaborative Note Editing
* **Decision:** Every note maintains a monotonically increasing integer `version` field. When updating a note (`PUT` / `PATCH`), the client must provide `expected_version`. The update executes atomically; if the current database version does not match `expected_version`, the server aborts the write and returns `409 Conflict`.
* **Why:** In shared team workspaces, concurrent edits are a primary failure mode. The naive "Last-Write-Wins" pattern silently overwrites data when two teammates edit simultaneously. Pessimistic locking (row-level locks) creates contention bottlenecks and breaks stateless REST semantics if a client disconnects mid-edit. OCC provides data integrity while keeping the API completely stateless.
* **Tradeoff:** Clients must handle `409 Conflict` by fetching the latest revision and prompting the user to resolve or merge differences.

### 3. Native PostgreSQL Full-Text Search with GIN Indexing vs. External Search Clusters
* **Decision:** Search is implemented using PostgreSQL's native `SearchVectorField`, `SearchQuery(search_type="websearch")`, `SearchRank`, and a `GIN` index (`GinIndex(fields=['search_vector'])`).
* **Why:** Running external search clusters (like Elasticsearch or Meilisearch) adds operational complexity, sync latency, and potential split-brain inconsistency. PostgreSQL full-text search provides linguistic stemming, relevance ranking, and web-style search operators (e.g. quotes for exact phrase, minus for exclusion) with zero replication lag and full ACID transactional guarantees.
* **Tradeoff:** High-volume text writes require vector re-indexing during updates. I keep indexing synchronized during note mutations within the service layer.

### 4. Service / Selector Layer (Clean Architecture)
* **Decision:** I decoupled business logic and query orchestration into `services.py` (atomic mutations, OCC validation, revision snapshotting) and `selectors.py` (tenant-scoped data access), keeping models and ViewSets thin.
* **Why:** Fat models create bloated domain objects tightly coupled to Django ORM internals, while fat views make code difficult to test without mocking HTTP request/response lifecycles. Isolating business transactions in plain Python functions ensures complete unit testability, deterministic database transactions (`@transaction.atomic`), and reusable business workflows.
* **Tradeoff:** Adds a layer of indirection compared to standard Django CRUD scaffolding, but significantly improves maintainability and test clarity.

### 5. Unified Personal Notes and Team Workspaces
* **Decision:** Notes can exist either as personal notes (`team = None`) or team notes (`team = Team`). Personal notes are strictly private to the author, while team notes inherit the team's RBAC hierarchy. An explicit action endpoint (`POST /api/v1/notes/{id}/share-to-team/`) enables moving or promoting a personal note into a team workspace.
* **Why:** Users frequently start drafting thoughts privately before sharing them with colleagues. Supporting personal notes out of the box eliminates the need for users to create dummy "personal teams", simplifying the user onboarding experience.
* **Tradeoff:** Selectors must handle both personal notes and team notes when constructing unified search or aggregate listings.

---

## What I Would Change, Add, or Stop Doing With More Time

1. **JWT Authentication & RFC 6750 Bearer Standard (`djangorestframework-simplejwt`):**
   * Currently, the service uses DRF's built-in token authentication (`Authorization: Token <token>`) backed by the database. In a higher-scale system, I would migrate to the RFC 6750 standard `Authorization: Bearer <jwt_token>` format with short-lived, cryptographically signed access tokens and sliding refresh tokens. This eliminates a database query on every authenticated request while enabling seamless multi-service SSO and token revocation via Redis blacklisting.
2. **Asynchronous Background Processing (Celery / Redis / Valkey):**
   * Move search vector re-indexing, export generation, and team invitation emails to background workers.
3. **Real-Time Collaborative Editing (CRDTs over WebSockets):**
   * While OCC prevents lost updates for asynchronous REST workflows, real-time simultaneous co-authoring (similar to Google Docs or Notion) would benefit from CRDTs (Conflict-free Replicated Data Types via Yjs) over Django Channels / WebSockets.
4. **Fine-Grained Resource Permissions (Object-Level ACLs):**
   * Extend the RBAC model to support per-note permission overrides (e.g. granting specific team members edit access to an otherwise read-only note).
5. **Rich Content Diffing and Semantic Search:**
   * Integrate structured JSON rich-text (ProseMirror / Block-based schema) and vector embeddings (pgvector) to provide hybrid keyword + semantic similarity search.
6. **Rate Limiting and Abuse Prevention:**
   * Configure Redis-backed rate limiting on authentication and search endpoints to prevent enumeration and denial-of-service vectors.

---

## Quick Start (Local Docker Setup)

The environment is containerized using Docker Compose and managed with `uv`.

> **Note on `.env.local`**:
> `.env.local` is intentionally committed to this repository to provide an instant, zero-friction local setup for reviewers. In production environments, credentials are provided via external secret managers.

### 1. Build and Run the Stack

```bash
docker compose -f local.yml up --build
```

The database will initialize, migrations will apply automatically on startup, and the API service will be accessible at:
* **API Base:** `http://localhost:8000`
* **Interactive Swagger UI:** `http://localhost:8000/api/docs/`
* **ReDoc Documentation:** `http://localhost:8000/api/redoc/`
* **OpenAPI 3.0 Schema:** `http://localhost:8000/api/schema/`
* **Django Admin:** `http://localhost:8000/admin/`
* **Health Check:** `http://localhost:8000/health/`

### 2. Create a Superuser (For Django Admin Access)

To inspect, moderate, or manage data in the Django Admin interface (`http://localhost:8000/admin/`):

```bash
# Interactive prompt:
docker compose -f local.yml exec django python manage.py createsuperuser

# Or non-interactive one-liner (Username: admin, Password: adminpassword123):
docker compose -f local.yml exec -e DJANGO_SUPERUSER_PASSWORD=adminpassword123 django python manage.py createsuperuser --noinput --username admin --email admin@example.com
```

### 3. Run the Test Suite

```bash
docker compose -f local.yml exec django pytest
```

### 4. Run Linter and Formatter (Ruff)

```bash
docker compose -f local.yml exec django ruff check .
docker compose -f local.yml exec django ruff format --check .
```

---

## API Reference and Workflow Guide

All protected endpoints require an `Authorization: Token <token>` header.

### Authentication Endpoints
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :---: |
| `POST` | `/api/v1/auth/register/` | Register a new user and receive auth token | No |
| `POST` | `/api/v1/auth/token/` | Obtain auth token with username and password | No |
| `GET` | `/api/v1/auth/me/` | Retrieve current user profile | Yes |
| `PATCH` | `/api/v1/auth/me/` | Update current user profile | Yes |
| `POST` | `/api/v1/auth/logout/` | Invalidate and revoke current auth token | Yes |

### Team Management Endpoints
| Method | Endpoint | Description | Access Rule |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/teams/` | List teams current user belongs to | Member |
| `POST` | `/api/v1/teams/` | Create team workspace (creator becomes OWNER) | Authenticated |
| `GET` | `/api/v1/teams/{id}/` | Retrieve team details | Member |
| `PATCH` | `/api/v1/teams/{id}/` | Update team details (name, description) | Owner / Admin |
| `DELETE` | `/api/v1/teams/{id}/` | Delete team workspace | Owner |
| `GET` | `/api/v1/teams/{id}/members/` | List team members with roles | Member |
| `POST` | `/api/v1/teams/{id}/members/add/` | Invite/add a user with a role | Owner / Admin |
| `PATCH` | `/api/v1/teams/{id}/members/{user_id}/role/` | Update member role | Owner / Admin |
| `DELETE` | `/api/v1/teams/{id}/members/{user_id}/` | Remove member or leave team | Owner / Admin / Self |

### Note Operations Endpoints
| Method | Endpoint | Description | Access Rule |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/notes/` | List accessible notes (supports `?team=`, `?personal=true`, `?tag=`, `?is_pinned=`) | Authenticated |
| `POST` | `/api/v1/notes/` | Create personal note (`team_id: null`) or team note | Authenticated (Non-Viewer) |
| `GET` | `/api/v1/notes/{id}/` | Retrieve note details and content | Author or Team Member |
| `PUT` | `/api/v1/notes/{id}/` | Update note (requires `expected_version` for OCC) | Author or Team Member (Non-Viewer) |
| `DELETE` | `/api/v1/notes/{id}/` | Soft-delete note (move to trash) or `?hard=true` | Author or Team Admin/Owner |
| `GET` | `/api/v1/notes/trash/` | List soft-deleted notes in trash | Author or Team Member |
| `POST` | `/api/v1/notes/{id}/restore/` | Restore soft-deleted note from trash | Author or Team Admin/Owner |
| `GET` | `/api/v1/notes/{id}/history/` | View revision history snapshots | Author or Team Member |
| `POST` | `/api/v1/notes/{id}/revert/` | Revert note content to a prior version number | Author or Team Member (Non-Viewer) |
| `POST` | `/api/v1/notes/{id}/share-to-team/` | Promote personal note into team workspace | Author |
| `GET` | `/api/v1/notes/search/?q={query}` | Ranked full-text search across accessible notes | Authenticated |

### Tag Management Endpoints
| Method | Endpoint | Description | Access Rule |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/notes/tags/` | List tags accessible to user (`?team={id}`) | Authenticated |
| `POST` | `/api/v1/notes/tags/` | Create a tag (personal or team-scoped) | Authenticated |

---

## Role-Based Access Control (RBAC) Matrix

| Permission | Owner | Admin | Member | Viewer |
| :--- | :---: | :---: | :---: | :---: |
| View Team Notes | Yes | Yes | Yes | Yes |
| Create Team Notes | Yes | Yes | Yes | No |
| Edit Shared Team Notes | Yes | Yes | Yes | No |
| View Private Notes in Team | Yes | Yes | Author Only | Author Only |
| Soft-Delete Any Note | Yes | Yes | Author Only | No |
| Add / Remove Members | Yes | Yes | No | No |
| Assign / Demote Owner Role | Yes | No | No | No |
| Delete Team Workspace | Yes | No | No | No |

---

## Testing Strategy and Modular Architecture

The test suite is modularized directly inside each domain application, separating service-level unit tests from HTTP/API integration tests:

### Core Tests (`apps/core/tests/`)
* **`test_health.py`**: Health check and basic service liveness.
* **`test_models.py`**: `SoftDeleteModel` and `SoftDeleteQuerySet` unit testing (`.active()`, `.deleted()`, `.soft_delete()`, `.restore()`).

### Users Tests (`apps/users/tests/`)
* **`test_api.py`**: User registration, duplicate username rejection, password confirmation validation, token generation, profile update (`PATCH /me/`), token revocation upon logout, and unauthenticated boundary enforcement.

### Teams Tests (`apps/teams/tests/`)
* **`test_services.py`**: Unit tests for team creation, member additions, role hierarchy invariants, and sole-owner protection.
* **`test_api.py`**: Integration tests for team workspaces, member roster listing, and non-existent user handling.
* **`test_permissions.py`**: Full RBAC permission matrix verification across all roles (`OWNER`, `ADMIN`, `MEMBER`, `VIEWER`, `OUTSIDER`).

### Notes Tests (`apps/notes/tests/`)
* **`test_services.py`**: Unit tests for note creation, version 1 snapshotting, Optimistic Concurrency Control conflicts, and historical revision reversion.
* **`test_tags.py`**: Personal tags, team-scoped tags, tag list scoping, and unique name constraints.
* **`test_search.py`**: Ranked PostgreSQL full-text search matching across title/body, tag filtering, and strict search tenant isolation (ensuring foreign team notes are never returned).
* **`test_api.py`**: Integration tests for personal vs. team notes, 409 Conflict handling, soft-delete and restore lifecycle, revision history endpoints, and personal-to-team note promotion.
* **`test_permissions.py`**: Exhaustive permission matrix for personal notes privacy, shared team notes, private team notes, and moderation delete rules.
* **`test_edge_cases.py`**: Pagination structure, pinned note filtering, missing `expected_version` validation, hard delete permanent purging, invalid reversion versions, and custom error JSON envelope structure.

---

## Step-by-Step API Workflow Guide

Follow this sequence to test all core features from terminal or API clients:

### 1. Register User Accounts
```bash
# Register Alice (Team Owner)
curl -X POST http://localhost:8000/api/v1/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "email": "alice@example.com", "password": "Password123!", "password_confirm": "Password123!", "first_name": "Alice", "last_name": "Smith"}'

# Register Bob (Team Member)
curl -X POST http://localhost:8000/api/v1/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"username": "bob", "email": "bob@example.com", "password": "Password123!", "password_confirm": "Password123!", "first_name": "Bob", "last_name": "Jones"}'
```

### 2. Obtain Auth Token (Login)
```bash
curl -X POST http://localhost:8000/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "Password123!"}'
# Response returns: {"token": "<ALICE_TOKEN>", "user": {...}}
```

### 3. Create a Team Workspace and Add Members
```bash
# Create Team Workspace (Alice becomes OWNER)
curl -X POST http://localhost:8000/api/v1/teams/ \
  -H "Authorization: Token <ALICE_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Engineering Core", "description": "Backend architecture team"}'
# Response returns: {"id": "<TEAM_ID>", "name": "Engineering Core", ...}

# Add Bob as a MEMBER (using Bob's user ID)
curl -X POST http://localhost:8000/api/v1/teams/<TEAM_ID>/members/add/ \
  -H "Authorization: Token <ALICE_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 2, "role": "MEMBER"}'
```

### 4. Create and Update a Personal Note (with OCC)
```bash
# Create a private personal note
curl -X POST http://localhost:8000/api/v1/notes/ \
  -H "Authorization: Token <ALICE_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"title": "Database Architecture", "body": "PostgreSQL full-text search and indexing strategies.", "team_id": null, "is_pinned": true}'
# Response returns: {"id": "<NOTE_ID>", "version": 1, ...}

# Update note successfully with matching expected_version (OCC)
curl -X PUT http://localhost:8000/api/v1/notes/<NOTE_ID>/ \
  -H "Authorization: Token <ALICE_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"title": "Database Architecture (v2)", "body": "Added GIN index benchmarks.", "expected_version": 1, "change_summary": "Added index benchmarks"}'
# Response returns: {"id": "<NOTE_ID>", "version": 2, ...}

# Attempting an update with a stale expected_version returns 409 Conflict
curl -X PUT http://localhost:8000/api/v1/notes/<NOTE_ID>/ \
  -H "Authorization: Token <ALICE_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"title": "Stale Edit", "expected_version": 1}'
# Response returns: HTTP 409 Conflict {"error": {"code": "conflict", "message": "Note was modified by another request..."}}
```

### 5. Promote Personal Note into Team Workspace
```bash
curl -X POST http://localhost:8000/api/v1/notes/<NOTE_ID>/share-to-team/ \
  -H "Authorization: Token <ALICE_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"team_id": "<TEAM_ID>", "visibility": "TEAM"}'
```

### 6. Search Notes using Full-Text Search
```bash
# Ranked full-text search matching 'PostgreSQL' across accessible notes
curl -X GET "http://localhost:8000/api/v1/notes/search/?q=PostgreSQL" \
  -H "Authorization: Token <ALICE_TOKEN>"
```

### 7. View Revision History and Revert to Prior Version
```bash
# View all audit snapshots
curl -X GET http://localhost:8000/api/v1/notes/<NOTE_ID>/history/ \
  -H "Authorization: Token <ALICE_TOKEN>"

# Revert content back to version 1
curl -X POST http://localhost:8000/api/v1/notes/<NOTE_ID>/revert/ \
  -H "Authorization: Token <ALICE_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"version_number": 1}'
```

### 8. Soft-Delete (Trash) and Restore
```bash
# Move note to trash
curl -X DELETE http://localhost:8000/api/v1/notes/<NOTE_ID>/ \
  -H "Authorization: Token <ALICE_TOKEN>"

# List notes in trash
curl -X GET http://localhost:8000/api/v1/notes/trash/ \
  -H "Authorization: Token <ALICE_TOKEN>"

# Restore note from trash
curl -X POST http://localhost:8000/api/v1/notes/<NOTE_ID>/restore/ \
  -H "Authorization: Token <ALICE_TOKEN>"
```

---

## Postman Collection

A pre-configured Postman collection is included at [`postman_collection.json`](file:///Users/cbz/Desktop/blue_notes/postman_collection.json).

### How to Use:
1. Open Postman and click **Import**.
2. Select the `postman_collection.json` file from this repository.
3. The collection is pre-configured with dynamic variables (`{{base_url}}`, `{{auth_token}}`, `{{team_id}}`, `{{note_id}}`, `{{note_version}}`).
4. Automated test scripts extract tokens and resource IDs sequentially from responses and propagate them automatically across subsequent requests.
5. Run the requests in folder order (`1. Authentication` -> `2. Teams` -> `3. Tags` -> `4. Notes` -> `5. Search` -> `6. Trash`).
