# Testing Deployed MCP Server with Claude Desktop

## Setup

1. **Open Claude Desktop configuration**:
```bash
open ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

2. **Add your deployed server**:
```json
{
  "mcpServers": {
    "customer-success-cloud": {
      "url": "Your MCP URL endpoint",
      "transport": "sse"
    }
  }
}
```

3. **Restart Claude Desktop**

4. **Test commands in Claude**:
```
"Authenticate as admin with password admin123"

"Create a CTA for account acct-456 with title 'Schedule QBR' and high priority"

"Update health score for account acct-456 to 92"

"List all health scores"

"Register a new user with username john_doe, email john@example.com, password SecurePass123"
```

## Why Claude Desktop?

- ✅ Full SSE transport support
- ✅ Works with deployed Cloud Run servers
- ✅ Better MCP protocol compatibility
- ✅ No local server needed

## VSCode Copilot Alternative

VSCode Copilot works best with **local** MCP servers using stdio transport.
See `.vscode/settings.json` for the local configuration.

To test the **deployed** server, Claude Desktop is currently the better option.
