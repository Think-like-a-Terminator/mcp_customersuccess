# Contributing to Customer Success MCP Server

Thank you for your interest in contributing! This guide will get you set up quickly.

---

## Table of Contents

- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Making Changes](#making-changes)
- [Running Tests](#running-tests)
- [Submitting a Pull Request](#submitting-a-pull-request)
- [Good First Issues](#good-first-issues)
- [Code Style](#code-style)

---

## Development Setup

### Prerequisites
- Python 3.10+
- Docker Desktop (for the local PostgreSQL instance)
- `uv` package manager

### 1 — Fork and clone

```bash
git clone https://github.com/<your-username>/mcp_customersuccess.git
cd mcp_customersuccess
```

### 2 — Create a virtual environment and install dependencies

```bash
uv venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Core deps
uv pip install -e .

# Optional integration deps (Slack, Salesforce, HubSpot)
uv pip install -e ".[integrations]"

# Dev tools
uv pip install pytest pytest-cov black ruff
```

### 3 — Start the database

```bash
docker compose up -d postgres
```

### 4 — Configure environment

```bash
cp .env.example .env
# Edit .env — at minimum set JWT_SECRET_KEY
```

### 5 — Run the server locally

```bash
uv run python -m src.server
# Server starts at http://localhost:8000
```

---

## Project Structure

```
src/
├── server.py  ← All MCP tool definitions + OAuth 2.1 endpoints
├── config.py            ← Settings (pydantic-settings, reads from .env)
├── models.py            ← Pydantic data models (CTA, HealthScore, RiskAlert…)
├── mcp_storage.py       ← PostgreSQL persistence for MCP tools
├── db_service.py        ← Raw PostgreSQL connection / query execution
├── auth.py              ← JWT helpers
├── oauth_service.py     ← OAuth 2.1 flow (PKCE, tokens, dynamic registration)
├── slack_service.py     ← Slack Incoming Webhook notifications
├── crm_service.py       ← Salesforce + HubSpot read-sync
├── user_service.py      ← User auth (used by OAuth login, not MCP tools)
└── api_key_service.py   ← Legacy X-API-Key auth (SSE middleware only)
```

**Key rule:** Admin operations (user management, API key rotation) are **not** exposed as MCP tools. They are performed out-of-band via direct database access or scripts in `src/utilities/`.

---

## Making Changes

### Adding a new MCP tool

1. Add the function decorated with `@mcp.tool()` in `src/server.py`.
2. Add any required Pydantic models to `src/models.py`.
3. Add persistence methods to `src/mcp_storage.py` (and the corresponding SQL in `init-db.sql` if a new table is needed).
4. Write a test in `src/tests/`.
5. Update the **Available Tools** table in `README.md`.

### Adding a new integration

1. Create `src/<name>_service.py` with a clean class interface.
2. Add configuration variables to `src/config.py` and `.env.example`.
3. Add optional pip dependency to `pyproject.toml` under `[project.optional-dependencies]`.
4. Expose a MCP tool (e.g. `sync_from_<name>`) in `server.py`.
5. Add the integration to the **Roadmap** / **Integrations** section of `README.md`.

---

## Running Tests

```bash
# All tests
uv run pytest

# With coverage
uv run pytest --cov=src --cov-report=term-missing

# Single file
uv run pytest src/tests/test_tools.py -v
```

Tests require a running PostgreSQL instance (the Docker Compose stack or set env vars pointing to your own instance).

---

## Code Style

- **Formatter:** `black` — run `uv run black src/` before committing.
- **Linter:** `ruff` — run `uv run ruff check src/`. Fix all warnings before submitting a PR.
- **Type hints:** Use them for all public functions. The CI will fail if `ruff` reports errors.
- **Docstrings:** Every `@mcp.tool()` function must have a complete docstring — it becomes the tool description visible in the LLM client.

---

## Submitting a Pull Request

1. Create a branch: `git checkout -b feat/my-feature`
2. Make your changes and add tests.
3. Run `uv run black src/ && uv run ruff check src/ && uv run pytest`.
4. Push and open a PR against `main`.
5. Fill in the PR template — describe what changed and why.

PRs are reviewed within a few days. Please keep them focused: one feature or fix per PR.

---

## Good First Issues

Look for issues tagged [`good first issue`](../../issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) on GitHub. Some ideas:

| Area | Task |
|---|---|
| **Notifications** | Add PagerDuty incident creation on `high` risk alerts |
| **CRM** | Add a `sync_from_crm` dry-run mode that previews changes without writing |
| **Health Scores** | Add a `compare_health_scores` tool that diffs two time periods |
| **Database** | Add query result pagination to `query_database` |
| **Docs** | Record a demo GIF showing the OAuth flow in Claude Desktop |
| **Tests** | Increase test coverage for `mcp_storage.py` |

---

## Questions?

Open a [GitHub Discussion](../../discussions) or file an issue. We're happy to help you get started.
