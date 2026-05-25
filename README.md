# Customer Success MCP Server

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that brings customer success operations directly into your AI assistant. Think of it as a lightweight, open-source Gainsight — letting LLM clients like Claude Desktop or A.I. Chats analyze data, manage CTAs, health scores, and risk alerts against a live PostgreSQL database, all secured by OAuth 2.1.

---

## Intended Audience (Who is this project for?)

The natural audience:
- **Startups and scale-ups** that need basic Customer Success Insights and aren't ready for a $1,200/month CS platform
- **Solo CSMs and small teams** who want AI tooling without an enterprise contract
- **Developers** who want to build AI-powered CS workflows and need a self-hosted, open-source foundation to extend
- **Companies already using Claude, Copilot, LLMs** who want CS operations inside their existing LLM client

## 🤔 Why This Project? (vs. Salesforce / HubSpot / Gainsight)

Salesforce, HubSpot, and Gainsight all have native concepts that are same or similar — health scores, tasks, alerts. So why does this exist?

### What the incumbents offer (and what it approximately costs)

| Concept | Salesforce native | HubSpot native | Gainsight |
|---|---|---|---|
| CTAs | Success Plans / Tasks (Success Cloud) | Tasks + Deal pipeline stages | ✅ Native |
| Health Scores | Einstein scoring or custom formula fields | Customer Health Score (Service Hub Enterprise only) | ✅ Native |
| Risk Alerts | Einstein Opportunity Scoring + Flow automations | Predictive Lead Scoring (Marketing Hub) | ✅ Native |

The catch: **these can be expensive and heavyweight.**
- Gainsight starts at approximately ~$1,200/month (estimate) and targets enterprise CS teams
- Salesforce Success Cloud runs ~$150–300/user/month (estimate)
- HubSpot Service Hub with health scoring is Enterprise tier only (~$1,200+/month, estimate)
- All three require significant admin setup before you get any value

### What makes this project different

**1. Free MCP server with quick setup and connection to existing LLM clients**

The core value isn't the data model. It's the interface layer. This project lets an AI assistant (Claude, ChatGPT, GitHub Copilot, Cursor, or any MCP-compatible client) natively call customer success operations as tool calls, with proper OAuth 2.1 authentication, with very little custom integration work. Let your A.I. LLM model do the analysis, risk-scoring, and predictive forecasts.

**2. It's a glue layer, not a replacement CRM**

The right mental model: your CRM (Salesforce, HubSpot, or even just a spreadsheet) holds the account data. This MCP server is the AI-native action surface on top of it. The `sync_from_crm` tool pulls your accounts in; the CTA, health score, and alert tools give your AI assistant structured ways to act on them — all inside your existing LLM workflow, without switching tabs.


### How to think about it

> *"An AI-native customer success layer for teams that don't need — or can't afford — Gainsight or Salesforce Success Cloud. Connects to your existing CRM data, lives inside your LLM client, and costs little to nothing to run if deployed."*

This isn't trying to replace Salesforce for a 500-person sales org. It's the tool that a 10-person SaaS company's founding CSM deploys on a Sunday afternoon and the team uses on Monday morning inside Claude Desktop or a chat client.

---

## 🎬 Demo

> **Coming soon** — a demo GIF showing the OAuth sign-in flow, creating a CTA, and getting a risk alert notification.
>
> To try it yourself right now: `docker compose up -d` → add to Claude Desktop → ask *"Let's create a CTA."*.

---

## ✨ Features

| Domain | What you can do |
|---|---|
| 📋 **Call to Actions (CTAs)** | Create, list, update, and retrieve CTAs per account with priority, owner, due dates, and tags |
| 💚 **Health Scores** | Track 0-100 health scores with weighted metrics, trend analysis, and status categories |
| ⚠️ **Risk Alerts** | Create, list, acknowledge, and inspect risk alerts with severity levels and recommended actions |
| 🗄️ **Database Queries** | Run SQL queries, list tables, inspect schemas, and test the connection against your PostgreSQL instance |
| 🔐 **Lazy OAuth 2.1** | Zero-credential-in-chat security: the server hands the LLM client an authorization URL; the user clicks it, logs in through their browser, and the session is automatically activated |
| 🔔 **Slack Notifications** | High/medium risk alerts are automatically posted to a Slack channel (set `SLACK_WEBHOOK_URL`) |
| 🔗 **CRM Sync** | Pull accounts from Salesforce or HubSpot into the database with one tool call |

---

## �� How Authentication Works (Lazy OAuth)

This server implements **lazy OAuth 2.1** — credentials are never typed into the chat window.

1. You (or your AI assistant) call any tool or `check_auth_status`.
2. If the session is not yet authenticated, the server returns a response containing a `sign_in_url`.
3. The LLM client surfaces that URL to you (e.g. *"Please sign in here: https://…/authorize"*).
4. You open the link in your browser, enter your username and password on the server's hosted login page, and approve access.
5. The server issues an OAuth access token bound to your session.
6. All subsequent tool calls in that session are automatically authorized — no password ever passes through the LLM.

> **Why this matters:** Your credentials are exchanged directly between your browser and the server over HTTPS. The LLM only ever sees an opaque session token, making it safe to use with any MCP-compatible client.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL 14+ (local Docker or Google Cloud SQL)
- `uv` package manager (or `pip`)

### 1 — Clone & install

```bash
git clone https://github.com/briany8285/mcp_customersuccess.git
cd mcp_customersuccess
uv venv && source .venv/bin/activate
uv pip install -e .
```

### 2 — Start the database (and full MCP server via Docker)

**Option A — Full stack with Docker (recommended for quick local testing):**

```bash
docker compose up -d   # starts MCP server + PostgreSQL; schema applied automatically
```

The MCP server will be available at `http://localhost:8000`. Skip steps 3 and 4 below — Docker Compose sets all required environment variables with sensible defaults.

**Option B — Database only (if you want to run the server manually):**

```bash
docker compose up -d postgres
```

Or point to an existing PostgreSQL instance via environment variables (see below).

### 3 — Configure environment (skip if using Docker Option A)

```bash
cp .env.example .env
```

Minimum required variables:

```env
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=customer_success
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-password

# Auth
JWT_SECRET_KEY=change-me-to-a-long-random-string

# Public URL the browser will reach (used in the sign-in link sent to the LLM client)
OAUTH_PUBLIC_BASE_URL=http://localhost:8000
```

### 4 — Run locally

```bash
uv run python -m src.server
```

The server starts on `http://localhost:8000`.

---

## 🛠️ Connecting to an LLM Client

### Claude Desktop

For a deployed server (SSE transport):

```json
{
  "mcpServers": {
    "customer-success": {
      "url": "https://your-cloud-run-url/sse",
      "transport": "sse"
    }
  }
}
```

Add this to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows).

For local development using stdio:

```json
{
  "mcpServers": {
    "customer-success-local": {
      "command": "uv",
      "args": ["--directory", "/path/to/mcp_customersuccess", "run", "python", "-m", "src.server"],
      "env": {
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PASSWORD": "your-password",
        "JWT_SECRET_KEY": "your-secret",
        "OAUTH_PUBLIC_BASE_URL": "http://localhost:8000"
      }
    }
  }
}
```

### GitHub Copilot (VS Code)

Create `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "customer-success": {
      "type": "sse",
      "url": "https://your-cloud-run-url/sse"
    }
  }
}
```

---

## 🧰 Available Tools

### 🔐 Authentication
| Tool | Description |
|---|---|
| `check_auth_status` | Check if the current session is authenticated; returns a `sign_in_url` if not |

### 📋 Call to Actions
| Tool | Description |
|---|---|
| `create_call_to_action` | Create a new CTA for an account |
| `list_call_to_actions` | List CTAs with optional filters (status, priority, owner) |
| `update_call_to_action` | Update a CTA's status, priority, owner, or due date |
| `get_call_to_action` | Get full details of a specific CTA |

### 💚 Health Scores
| Tool | Description |
|---|---|
| `update_health_score` | Set or update an account's health score with weighted metrics |
| `get_health_score` | Get the current health score for an account |
| `list_health_scores` | List health scores with optional status/threshold filters |

### ⚠️ Risk Alerts
| Tool | Description |
|---|---|
| `create_risk_alert` | Create a new risk alert with severity, factors, and recommended actions |
| `list_risk_alerts` | List alerts with filters (risk level, acknowledgment status) |
| `acknowledge_risk_alert` | Mark a risk alert as acknowledged |
| `get_risk_alert` | Get full details of a specific alert |

### 🗄️ Database
| Tool | Description |
|---|---|
| `query_database` | Execute a SQL query against PostgreSQL |
| `get_database_tables` | List all tables in the database |
| `get_table_schema` | Inspect columns and data types for a table |
| `test_database_connection` | Verify the database connection is healthy |

### 🔗 CRM Integrations
| Tool | Description |
|---|---|
| `sync_from_crm` | Pull accounts from Salesforce or HubSpot into the database |

> **Admin operations** (user management, API key rotation, etc.) are intentionally **not** exposed as MCP tools.  
> Perform them out-of-band via direct database access or the scripts in `src/utilities/`.

---

## 🔔 Slack Notifications

Set `SLACK_WEBHOOK_URL` in your environment and any **medium or high** risk alert created via `create_risk_alert` will automatically post a rich notification to your Slack channel.

**Setup:**
1. Go to [https://api.slack.com/apps](https://api.slack.com/apps) → Create New App → Incoming Webhooks
2. Activate Incoming Webhooks and add a webhook to your desired channel
3. Copy the Webhook URL into your `.env`:

```env
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T.../B.../...
```

Required package (already in optional extras):
```bash
pip install slack-sdk
# or: pip install ".[slack]"
```

---

## 🔗 CRM Integrations

Use the `sync_from_crm` tool to pull account data from your CRM directly into the `customers` table, giving all other tools (CTAs, health scores, alerts) live account context.

### Salesforce

```env
SALESFORCE_USERNAME=you@company.com
SALESFORCE_PASSWORD=your-sf-password
SALESFORCE_SECURITY_TOKEN=your-security-token
SALESFORCE_DOMAIN=login   # use "test" for sandboxes
```

```bash
pip install simple-salesforce
# or: pip install ".[salesforce]"
```

Then in your LLM client:
```
sync_from_crm(crm="salesforce")
```

### HubSpot

```env
HUBSPOT_API_KEY=pat-na1-...
```

Create a HubSpot Private App at [https://app.hubspot.com/api-keys](https://app.hubspot.com/api-keys) with `crm.objects.companies.read` scope.

```bash
pip install hubspot-api-client
# or: pip install ".[hubspot]"
```

Then in your LLM client:
```
sync_from_crm(crm="hubspot")
```

### Install all integrations at once

```bash
pip install ".[integrations]"
```

---

## ☁️ Production Deployment (Google Cloud Run)

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for the full guide. The short version:

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud builds submit --config=cloudbuild.yaml
```

The `cloudbuild.yaml` builds the Docker image, pushes it to Artifact Registry, and deploys to Cloud Run with the Cloud SQL Auth Proxy for secure database connectivity.

**Recommended production setup:**
- Google Cloud Run (auto-scaling, `min-instances=1` to avoid cold-start auth delays)
- Google Cloud SQL (PostgreSQL 15) with private IP
- Google Secret Manager for `JWT_SECRET_KEY` and `POSTGRES_PASSWORD`
- Google Cloud Armor for rate limiting / WAF

---

## 🏗️ Architecture

```
mcp_customersuccess/
├── src/
│   ├── server.py             # MCP server — all tool definitions + OAuth 2.1 endpoints
│   ├── auth.py               # JWT token generation and validation
│   ├── config.py             # Settings loaded from environment variables
│   ├── models.py             # Pydantic data models
│   ├── db_service.py         # PostgreSQL connection and query execution
│   ├── mcp_storage.py        # CTA, health score, and risk alert persistence
│   ├── user_service.py       # User auth (used by the OAuth login flow, not exposed as tools)
│   ├── api_key_service.py    # Legacy X-API-Key auth for the SSE middleware
│   ├── slack_service.py      # Slack Incoming Webhook notifications
│   ├── crm_service.py        # Salesforce + HubSpot read-sync
│   └── email_service.py      # SMTP / AWS SES (optional)
├── init-db.sql               # Database schema and seed data
├── docker-compose.yml        # Local dev stack (MCP + PostgreSQL)
├── Dockerfile
├── cloudbuild.yaml           # Google Cloud Build → Cloud Run pipeline
├── pyproject.toml
├── CONTRIBUTING.md
└── docs/
    ├── DEPLOYMENT.md
    ├── QUICKSTART_DEPLOY.md
    └── TESTING_WITH_CLAUDE.md
```

---

## 🔒 Security Model

| Concern | How it's handled |
|---|---|
| Credentials passing through the LLM | **Never** — OAuth 2.1 redirects authentication to the user's browser |
| Session tokens | Short-lived JWTs; sessions are cleaned up when the MCP session closes |
| Admin operations | Done **outside** the MCP server via direct DB access or `src/utilities/` scripts |
| HTTPS | Enforced by Cloud Run; use nginx/Caddy in front of the local server if needed |

---

## 🧪 Development

```bash
uv run pytest          # run tests
uv run black src/      # format
uv run ruff check src/ # lint
```

---

## 🤝 Contributing

Contributions are very welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide — dev setup, code style, and how to add new tools or integrations.

Look for [`good first issue`](../../issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) tags on GitHub.

---

## 📚 Resources

- [Model Context Protocol spec](https://modelcontextprotocol.io)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [OAuth 2.1 draft](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1)
- [Google Cloud Run docs](https://cloud.google.com/run/docs)
