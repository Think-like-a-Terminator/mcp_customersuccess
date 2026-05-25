# Testing the MCP Server with Claude Desktop

## Setup

### 1. Open Claude Desktop configuration

```bash
# macOS
open ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

### 2. Add your server

**Deployed server (SSE transport — recommended):**
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

**Local development (stdio transport):**
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

### 3. Restart Claude Desktop

---

## How Sign-In Works (Lazy OAuth)

You **never** type your password into Claude. Instead:

1. Ask Claude to `check_auth_status` or try any tool.
2. Claude replies with something like:
   > *"You need to sign in first. Please visit: https://your-server/authorize"*
3. Click the link — a login page opens in your browser.
4. Enter your credentials directly on the server's hosted page.
5. After approval, your session is activated automatically.
6. Tell Claude the session is ready; it will confirm via `check_auth_status`.

---

## Example Prompts

### Check authentication
```
Check if I'm authenticated
```

### Call to Actions
```
Create a CTA for account acct-456 with title "Schedule QBR", high priority, due in 14 days

List all open CTAs for account acct-456

Update CTA <id> status to "completed"
```

### Health Scores
```
Update health score for account acct-456 to 85 with metrics:
  - usage: 90, weight 0.4
  - engagement: 80, weight 0.3
  - support: 85, weight 0.3
  trend: improving

List all accounts with health score below 60
```

### Risk Alerts
```
Create a high-risk alert for account acct-789 with factors:
  "Low product usage", "Missed two QBRs"
  Recommended actions: "Schedule executive call", "Send usage report"

List all unacknowledged high-risk alerts

Acknowledge risk alert <id>
```

### Database
```
Show me all tables in the database

What columns does the health_scores table have?

Run this query: SELECT account_id, overall_score FROM health_scores WHERE overall_score < 50
```

---

## Why Claude Desktop?

- ✅ Full SSE transport support for deployed servers
- ✅ Handles the OAuth redirect flow cleanly
- ✅ No credentials ever enter the chat
- ✅ Works with both local (stdio) and remote (SSE) deployments

## VS Code / GitHub Copilot

Copilot also supports MCP via `.vscode/mcp.json`. Use SSE transport pointing to your deployed Cloud Run URL, or stdio for a local server. The OAuth flow works the same way — Copilot will surface the sign-in URL for you to click.
