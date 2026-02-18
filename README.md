# Customer Success MCP Server

A Model Context Protocol (MCP) server that provides customer success management tools similar to Gainsight. This server enables AI assistants to manage customer success operations including Call to Actions, Health Scores, and risk alerts.

## Features

### 🔐 Authentication & Security
- **JWT-based authentication** system with role-based access control
- **API Key authentication** for multi-network access (LibreChat, external clients)
- **User registration** with email verification
- Secure token and API key management
- See [API_KEY_SETUP.md](API_KEY_SETUP.md) for API key configuration

### 📋 Call to Actions (CTAs)
- Create, update, and manage CTAs for accounts
- Priority levels and status tracking
- Assignment and due date management
- Tag-based categorization
- **Persistent storage in PostgreSQL**

### 💚 Health Score Tracking
- Track overall account health scores (0-100)
- Multiple metrics with weighted calculations
- Status categories (Excellent, Good, At Risk, Critical)
- Trend analysis (improving, declining, stable)
- **Persistent storage in PostgreSQL**

### ⚠️ Account Risk Alerts
- Create and manage risk alerts for accounts
- Risk level categorization (None, Low, Medium, High)
- Impact scoring and recommended actions
- Alert acknowledgment workflow
- **Persistent storage in PostgreSQL**

### 🗄️ Database Queries
- Execute SQL queries against PostgreSQL (Google Cloud SQL or local)
- Inspect table schemas and list available tables
- Support for standard PostgreSQL syntax

## Installation

### Prerequisites
- Python 3.10 or higher
- **PostgreSQL 14+** — either [Google Cloud SQL](https://cloud.google.com/sql/docs/postgres) for production or a local instance for development
- AWS account with SES configured (optional, for user registration email verification)
- `uv` package manager (recommended) or `pip`

### Setup

1. **Clone or navigate to the project directory:**
   ```bash
   cd /Users/briany/Documents/csmcp
   ```

2. **Install dependencies using uv:**
   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install -e .
   ```

   Or with pip:
   ```bash
   pip install -e .
   ```

3. **Set up the PostgreSQL database:**

   **Option A — Local (Docker, quickest for development):**
   ```bash
   docker compose up -d
   ```
   This starts PostgreSQL, the MCP server, and MailHog (local SMTP) together. The database schema is applied automatically via `init-db.sql`.

   **Option B — Google Cloud SQL:**
   - Create a PostgreSQL 15 instance in [Cloud SQL](https://console.cloud.google.com/sql)
   - Create a database named `customer_success`
   - Connect via Cloud SQL Auth Proxy or private IP
   - Apply the schema: `psql -h <HOST> -U postgres -d customer_success -f init-db.sql`

4. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and configure:
   - **PostgreSQL connection** (required):
     - `POSTGRES_HOST`: Database host (e.g., `localhost` or Cloud SQL private IP)
     - `POSTGRES_PORT`: Port, default `5432`
     - `POSTGRES_DB`: Database name, default `customer_success`
     - `POSTGRES_USER`: Database user, default `postgres`
     - `POSTGRES_PASSWORD`: Database password
   - `JWT_SECRET_KEY`: Change to a secure random string
   - AWS SES credentials (optional, for survey email features)
   - SMTP credentials (optional, for verification emails)

## Usage

### Running the Server

#### For Local Testing
```bash
uv run python -m src.server
```

#### Configure with Claude Desktop

Add to your Claude Desktop configuration (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "customer-success": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/briany/Documents/dfenterprisemcp",
        "run",
        "python",
        "-m",
        "src.server"
      ],
      "env": {
        "JWT_SECRET_KEY": "your-secret-key",
        "POSTGRES_HOST": "your-db-host",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "customer_success",
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": "your-db-password",
        "AWS_ACCESS_KEY_ID": "your-aws-key",
        "AWS_SECRET_ACCESS_KEY": "your-aws-secret",
        "AWS_REGION": "us-east-1",
        "SES_FROM_EMAIL": "noreply@yourdomain.com"
      }
    }
  }
}
```

#### Configure with VS Code

Create `.vscode/mcp.json`:

```json
{
  "servers": {
    "customer-success": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "--directory",
        "/Users/briany/Documents/csmcp",
        "run",
        "python",
        "-m",
        "src.server"
      ]
    }
  }
}
```

### Available Tools

#### Authentication & User Management
- **authenticate**: Get an access token for API access
- **register_user**: Register a new user account (with email verification)
- **verify_user_email**: Verify email with verification code
- **resend_verification_email**: Resend verification email
- **list_users**: List all registered users (admin only)

#### API Key Management
- **generate_api_key**: Generate new API keys for client authentication (admin only)
- **list_api_keys**: List all API keys with metadata
- **revoke_api_key**: Deactivate an API key
- **delete_api_key**: Permanently delete an API key

#### Call to Actions
- **create_call_to_action**: Create a new CTA
- **list_call_to_actions**: List CTAs with filters
- **update_call_to_action**: Update CTA status, priority, etc.
- **get_call_to_action**: Get details of a specific CTA

#### Health Scores
- **update_health_score**: Set or update account health score
- **get_health_score**: Get health score for an account
- **list_health_scores**: List health scores with filters

#### Risk Alerts
- **create_risk_alert**: Create a new risk alert
- **list_risk_alerts**: List risk alerts with filters
- **acknowledge_risk_alert**: Acknowledge a risk alert
- **get_risk_alert**: Get details of a specific alert

#### Database Tools
- **query_database**: Execute SQL queries against PostgreSQL
- **get_database_tables**: List all tables in the database
- **get_table_schema**: Inspect columns and types for a specific table
- **test_database_connection**: Verify the database connection is healthy

## Default Users

For testing purposes, the server includes default users:

- **Admin User**
  - Username: `admin`
  - Password: `admin123`
  - Access: Full read/write/admin permissions

- **CSM User**
  - Username: `csm`
  - Password: `csm123`
  - Access: Read/write permissions

**⚠️ Important:** Change these passwords in production!

## Example Usage

### 1. Authenticate
```
Use the authenticate tool with username "admin" and password "admin123"
```

### 2. Create a Call to Action
```
Use create_call_to_action with:
- account_id: "acct-001"
- title: "Conduct QBR"
- description: "Schedule quarterly business review"
- priority: "high"
- due_date_days: 14
```

### 3. Update Health Score
```
Use update_health_score with:
- account_id: "acct-001"
- overall_score: 85
- metrics: [
    {"name": "usage", "value": 90, "weight": 0.4},
    {"name": "engagement", "value": 80, "weight": 0.3}
  ]
- trend: "improving"
```

### 4. Create Risk Alert
```
Use create_risk_alert with:
- account_id: "acct-002"
- risk_level: "high"
- risk_factors: ["Low product usage", "Unresponsive to emails"]
- impact_score: 85
- recommended_actions: ["Schedule executive call", "Review usage data"]
```

## AWS SES Setup

To use AWS SES for registering users with email verification:

1. **Create AWS Account** and configure SES
2. **Verify your sender email** address in SES
3. **Move out of SES sandbox** for production use
4. **Configure credentials** in `.env`:
   ```
   AWS_ACCESS_KEY_ID=your-key
   AWS_SECRET_ACCESS_KEY=your-secret
   AWS_REGION=us-east-1
   SES_FROM_EMAIL=noreply@yourdomain.com
   ```

**Note:** Without AWS credentials, the server runs in mock mode for email sending (prints to console instead).

## Data Storage

All data is persisted in **PostgreSQL** (Google Cloud SQL in production, or a local Docker container for development). The schema is defined in `init-db.sql` and is applied automatically when using Docker Compose.

For production:
- Use Google Cloud SQL (PostgreSQL 15) with private IP access
- Enable automated backups and point-in-time recovery
- Store `POSTGRES_PASSWORD` and `JWT_SECRET_KEY` in Google Secret Manager
- See `cloudbuild.yaml` for the Cloud Run deployment pipeline

## Security Considerations

- Change default passwords immediately
- Use strong JWT secret keys
- Rotate tokens regularly
- Implement rate limiting
- Use HTTPS in production
- Store AWS credentials securely
- Implement proper error handling
- Add audit logging
- Regular security updates

## Development

### Running Tests
```bash
uv run pytest
```

### Code Formatting
```bash
uv run black src/
```

### Linting
```bash
uv run ruff check src/
```

## Architecture

```
cs_cloud_mcp/
├── src/
│   ├── __init__.py
│   ├── server.py          # Main MCP server with all tool definitions
│   ├── auth.py            # JWT authentication logic
│   ├── config.py          # Settings loaded from environment variables
│   ├── models.py          # Pydantic data models
│   ├── db_service.py      # PostgreSQL connection and query execution
│   ├── mcp_storage.py     # CTA, health score, and risk alert persistence
│   ├── user_service.py    # User registration, verification, and management
│   └── email_service.py   # SMTP / AWS SES email service
├── init-db.sql            # Database schema and seed data
├── docker-compose.yml     # Local dev stack (MCP server + PostgreSQL + MailHog)
├── Dockerfile
├── cloudbuild.yaml        # Google Cloud Build → Cloud Run deployment
├── pyproject.toml         # Project dependencies
├── .env.example           # Environment variables template
├── .gitignore
└── README.md
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - feel free to use this in your own projects!

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Check the MCP documentation: https://modelcontextprotocol.io
- Join the MCP community discussions

## Roadmap

Future enhancements:
- [ ] Advanced analytics and reporting
- [ ] Advanced risk scoring algorithms
- [ ] Webhook integrations
- [ ] Comprehensive test coverage

---

Built with ❤️ using the Model Context Protocol
