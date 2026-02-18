# API Key Authentication Setup Guide

## Overview

The Customer Success MCP Server now supports API key authentication, allowing secure access from multiple clients across different networks. This is essential for deployments where you want to:

- Deploy the MCP server on Google Cloud Run (or any cloud platform)
- Connect from multiple LLM clients (LibreChat, OpenWebUI, etc.)
- Access the server from different networks/locations
- Maintain secure authentication without exposing the server publicly

## How It Works

1. **API Key Generation**: Admins generate API keys using the `generate_api_key` tool
2. **Key Storage**: Keys are hashed (SHA256) and stored in PostgreSQL database
3. **Authentication**: Clients include the API key in the `X-API-Key` HTTP header
4. **Validation**: The server validates the key on every request (except `/health`)

## Security Features

- ✅ **SHA256 Hashing**: API keys are hashed before storage (never stored in plaintext)
- ✅ **One-Time Display**: Plaintext keys are only shown once during creation
- ✅ **Expiration Support**: Keys can have expiration dates
- ✅ **Revocation**: Keys can be deactivated without deletion (audit trail)
- ✅ **Activity Tracking**: Last used timestamp is updated on each validation
- ✅ **Key Prefixes**: First 8 characters shown for identification (e.g., `csm_live_`)

## Step 1: Generate an API Key

⚠️ **ADMIN ONLY**: API key management tools (generate, list, revoke, delete) can only be used by API keys that were created by "admin". This ensures only authorized administrators can manage API keys.

### Using MCP Tools (via Claude Desktop, MCP Inspector, etc.)

```python
# Generate a key that never expires
# Note: created_by is auto-detected from the calling API key
generate_api_key(
    name="LibreChat Production",
    description="API key for LibreChat on Google Cloud Run"
)

# Generate a key with 1-year expiration
generate_api_key(
    name="Test Client",
    description="Temporary key for testing",
    expires_in_days=365
)
```

### Response Example

```json
{
    "success": true,
    "message": "API key created successfully",
    "api_key": "csm_live_AbCdEfGhIjKlMnOpQrStUvWxYz123456",
    "key_id": 1,
    "key_prefix": "csm_live_",
    "name": "LibreChat Production",
    "created_by": "admin",
    "expires_at": null,
    "warning": "⚠️ Store this API key securely! You won't be able to retrieve it again."
}
```

**⚠️ CRITICAL**: Copy and save the `api_key` value immediately. You cannot retrieve it later!

### First-Time Setup (Bootstrap)

For the very first API key generation, you'll need to:

1. Create a bootstrap API key directly in the database with `created_by='admin'`
2. Use this bootstrap key to generate additional keys via the API

**Bootstrap script** (run once):
```bash
python -c "
from src.api_key_service import APIKeyService
service = APIKeyService()
result = service.create_api_key(
    name='Bootstrap Admin Key',
    description='Initial admin key for bootstrapping',
    created_by='admin'
)
print(f'Bootstrap API Key: {result[\"api_key\"]}')
print('Save this key securely!')
"
```

Once you have the bootstrap key, use it to generate additional keys via the API.

## Step 2: Configure Your Client

### LibreChat Configuration

Edit your LibreChat environment configuration:

```yaml
# LibreChat docker-compose.yml or .env
MCP_SERVERS: |
  {
    "customer-success": {
      "url": "https://customer-success-mcp-316962419897.us-central1.run.app",
      "transport": "sse",
      "headers": {
        "X-API-Key": "csm_live_AbCdEfGhIjKlMnOpQrStUvWxYz123456"
      }
    }
  }
```

### MCP Inspector (for testing)

```bash
# Launch MCP Inspector with API key header
npx @modelcontextprotocol/inspector sse \
  https://customer-success-mcp-316962419897.us-central1.run.app \
  --header "X-API-Key: csm_live_AbCdEfGhIjKlMnOpQrStUvWxYz123456"
```

### Claude Desktop Configuration

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "customer-success": {
      "url": "https://customer-success-mcp-316962419897.us-central1.run.app",
      "transport": "sse",
      "headers": {
        "X-API-Key": "csm_live_AbCdEfGhIjKlMnOpQrStUvWxYz123456"
      }
    }
  }
}
```

### Custom Client (Python Example)

```python
import httpx

# Connect to MCP server with API key
headers = {
    "X-API-Key": "csm_live_AbCdEfGhIjKlMnOpQrStUvWxYz123456",
    "Content-Type": "application/json"
}

async with httpx.AsyncClient() as client:
    # Check health (no auth required)
    response = await client.get(
        "https://customer-success-mcp-316962419897.us-central1.run.app/health"
    )
    print(response.json())
    
    # Connect to SSE endpoint (auth required)
    response = await client.get(
        "https://customer-success-mcp-316962419897.us-central1.run.app/sse",
        headers=headers
    )
```

### cURL Example

```bash
# Test health endpoint (no auth)
curl https://customer-success-mcp-316962419897.us-central1.run.app/health

# Test SSE endpoint with API key
curl -H "X-API-Key: csm_live_AbCdEfGhIjKlMnOpQrStUvWxYz123456" \
     https://customer-success-mcp-316962419897.us-central1.run.app/sse
```

## Step 3: Manage API Keys

⚠️ **ADMIN ONLY**: All API key management operations require an admin API key.

### List All API Keys

```python
# List all keys (admin only)
list_api_keys()

# List keys created by specific user
list_api_keys(created_by="admin")
```

Response:
```json
{
    "success": true,
    "count": 2,
    "keys": [
        {
            "id": 1,
            "key_prefix": "csm_live_",
            "name": "LibreChat Production",
            "description": "API key for LibreChat",
            "created_by": "admin",
            "is_active": true,
            "last_used_at": "2024-01-15T10:30:00",
            "expires_at": null,
            "created_at": "2024-01-01T00:00:00"
        }
    ]
}
```

### Revoke an API Key

```python
# Deactivate a key (keeps audit history, admin only)
revoke_api_key(key_id=1)
```

Response:
```json
{
    "success": true,
    "message": "API key 1 has been revoked",
    "key_id": 1,
    "revoked_at": "2024-01-15T10:35:00"
}
```

### Delete an API Key (Permanent)

```python
# ⚠️ Permanently delete (cannot be undone, admin only)
delete_api_key(key_id=1)
```

Response:
```json
{
    "success": true,
    "message": "API key 1 has been permanently deleted",
    "key_id": 1
}
```

## Multi-Network Deployment Architecture

```
┌─────────────────┐
│   LibreChat     │ (Network A: Google Cloud Run)
│   Container     │
└────────┬────────┘
         │ X-API-Key: csm_live_ABC...
         │
         ▼
┌─────────────────────────────────┐
│  Customer Success MCP Server    │ (Google Cloud Run)
│  ┌──────────────────────────┐   │
│  │ APIKeyMiddleware         │   │
│  │ • Validates X-API-Key    │   │
│  │ • Checks expiration      │   │
│  │ • Updates last_used_at   │   │
│  └──────────────────────────┘   │
│  ┌──────────────────────────┐   │
│  │ MCP Tools (29 total)     │   │
│  │ • 25 original tools      │   │
│  │ • 4 API key mgmt tools   │   │
│  └──────────────────────────┘   │
└─────────────────┬───────────────┘
                  │
         ┌────────┼────────┐
         │                 │
         ▼                 ▼
┌─────────────┐   ┌─────────────┐
│ PostgreSQL  │   │ AWS SES     │
│ Database    │   │ (Emails)    │
└─────────────┘   └─────────────┘


┌─────────────────┐
│  External LLM   │ (Network B: Different location)
│  Client         │
└────────┬────────┘
         │ X-API-Key: csm_live_XYZ...
         │
         └─────────────────────────────┐
                                       │
                                       ▼
                         (Same MCP Server, different API key)
```

## API Key Format

All API keys follow this format:
```
csm_live_<32_random_characters>
```

Example: `csm_live_AbCdEfGhIjKlMnOpQrStUvWxYz123456`

- `sk_` = Secret Key prefix
- `live_` = Environment indicator (live/production)
- Last 32 chars = Cryptographically secure random token

## Database Schema

```sql
CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    key_hash TEXT UNIQUE NOT NULL,        -- SHA256 hash of the key
    key_prefix TEXT NOT NULL,             -- First 8 chars for display
    name TEXT NOT NULL,                   -- Friendly name
    description TEXT,                     -- Purpose/notes
    created_by TEXT NOT NULL,             -- Username of creator
    is_active BOOLEAN DEFAULT TRUE,       -- Active status
    last_used_at TIMESTAMP,               -- Last authentication
    expires_at TIMESTAMP,                 -- Expiration date (null = never)
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_active ON api_keys(is_active);
CREATE INDEX idx_api_keys_created_by ON api_keys(created_by);
```

## Troubleshooting

### Error: "Admin access required"

**Problem**: Trying to use API key management tools with a non-admin API key.

**Cause**: Only API keys with `created_by='admin'` can manage other keys.

**Solution**: 
1. Use your bootstrap admin API key for key management operations
2. If you lost your admin key, create a new one directly in the database:
```bash
python -c "
from src.api_key_service import APIKeyService
service = APIKeyService()
result = service.create_api_key(
    name='Recovery Admin Key',
    description='Admin key for recovery',
    created_by='admin'
)
print(f'Admin API Key: {result[\"api_key\"]}')
"
```

### Error: "Missing X-API-Key header"

**Problem**: Request doesn't include the API key header.

**Solution**: Add `X-API-Key` header to your client configuration.

```bash
# Correct
curl -H "X-API-Key: csm_live_..." https://your-server.com/sse

# Incorrect (missing header)
curl https://your-server.com/sse
```

### Error: "Invalid or expired API key"

**Possible causes**:
1. **Wrong key**: Check that you copied the full API key correctly
2. **Revoked key**: Key was deactivated using `revoke_api_key`
3. **Expired key**: Key passed its `expires_at` date
4. **Deleted key**: Key was permanently removed

**Solution**:
```python
# List keys to check status
list_api_keys()

# Generate a new key if needed
generate_api_key(
    name="New Key",
    description="Replacement for expired key",
    created_by="admin"
)
```

### Health Check Works but SSE Fails

**Problem**: `/health` endpoint returns 200 but `/sse` returns 401.

**Explanation**: Health check doesn't require authentication (by design).

**Solution**: Add `X-API-Key` header to SSE requests.

### Key Not Working After Creation

**Common mistake**: Typo in the API key.

**Solution**: 
- API keys are case-sensitive
- Must include the full key: `csm_live_...` (not just the random part)
- Check for extra spaces or newlines when copying

## Best Practices

### 1. Key Management
- ✅ **Generate separate keys** for each client/environment
- ✅ **Use descriptive names**: "LibreChat Production", "Dev Testing", etc.
- ✅ **Set expiration dates** for temporary access
- ✅ **Revoke unused keys** instead of deleting (keeps audit trail)
- ✅ **Bootstrap key security**: Keep your initial admin bootstrap key extremely secure

### 2. Security
- ✅ **Never commit keys** to version control
- ✅ **Use environment variables** in client configs
- ✅ **Rotate keys regularly** (e.g., every 90-365 days)
- ✅ **Monitor `last_used_at`** to detect unused or compromised keys
- ✅ **Admin keys only**: Only API keys with `created_by='admin'` can manage other keys

### 3. Access Control
- ✅ **Admin API keys**: Use for key management and administrative tasks
- ✅ **Client API keys**: Generate separate keys for each application (LibreChat, external clients)
- ✅ **Client keys have full tool access**: All non-admin tools are accessible
- ✅ **No user registration required**: API key authentication replaces per-user accounts

### 3. Production Deployment
- ✅ **Enable HTTPS** (Cloud Run does this automatically)
- ✅ **Use different keys** for production vs. development
- ✅ **Document key owners** in the `description` field
- ✅ **Set up monitoring** for authentication failures

### 4. Key Rotation Process

```python
# Step 1: Generate new key (requires admin API key)
new_key = generate_api_key(
    name="LibreChat Production v2",
    description="Rotation of key #1",
    expires_in_days=365
)

# Step 2: Update client configuration with new key
# (Deploy updated config to LibreChat/clients)

# Step 3: Verify new key works
list_api_keys()  # Check last_used_at for new key

# Step 4: Revoke old key (after confirming new key works)
revoke_api_key(key_id=1)
```

## Environment Variables

No additional environment variables needed for API key auth! The system uses the existing PostgreSQL database configured in your `.env`:

```bash
# PostgreSQL connection (already configured)
DB_HOST=your-postgres-host
DB_PORT=5432
DB_NAME=customer_success
DB_USER=postgres
DB_PASSWORD=your-password
```

## Testing

### 1. Local Testing (Docker)

```bash
# Start server with PostgreSQL
docker-compose up -d

# Generate API key
python -c "
from src.api_key_service import APIKeyService
service = APIKeyService()
result = service.create_api_key('Test Key', 'Local testing', 'admin')
print(f'API Key: {result[\"api_key\"]}')
"

# Test with curl
curl -H "X-API-Key: <your-key>" http://localhost:8000/sse
```

### 2. Cloud Testing (Google Cloud Run)

```bash
# Test health (no auth)
curl https://customer-success-mcp-316962419897.us-central1.run.app/health

# Test SSE with valid key (should work)
curl -H "X-API-Key: csm_live_..." \
     https://customer-success-mcp-316962419897.us-central1.run.app/sse

# Test SSE without key (should fail with 401)
curl https://customer-success-mcp-316962419897.us-central1.run.app/sse
```

### 3. MCP Inspector Testing

```bash
# Install MCP Inspector (if not already installed)
npm install -g @modelcontextprotocol/inspector

# Launch with API key
npx @modelcontextprotocol/inspector sse \
  https://customer-success-mcp-316962419897.us-central1.run.app \
  --header "X-API-Key: csm_live_..."

# Access at: http://localhost:6274
```

## Rate Limiting (Not Implemented)

**Note**: Rate limiting is intentionally not implemented per user request. If you need rate limiting in the future, consider:

- Nginx/API Gateway rate limiting (external to MCP server)
- Cloud Run request quotas
- Database-level request tracking in `api_keys` table

## Migration from JWT to API Keys

If you're currently using JWT authentication:

1. **API keys replace JWT for transport-level auth** (SSE/HTTP requests)
2. **JWT still used for tool-level permissions** (if needed in future)
3. **Backward compatible**: Existing tools work without changes

**Migration steps**:
1. Run database migration (api_keys table already in `init-db.sql`)
2. Generate API keys for existing clients
3. Update client configurations with `X-API-Key` header
4. Test connections
5. (Optional) Retire JWT-based auth if no longer needed

## Support

For issues or questions:
- Check [TESTING_WITH_CLAUDE.md](TESTING_WITH_CLAUDE.md) for testing guides
- Review [DEPLOYMENT.md](DEPLOYMENT.md) for deployment troubleshooting
- Check server logs: `gcloud run logs read --service customer-success-mcp`

## Summary

✅ **API keys enable secure, multi-network access to your MCP server**
✅ **Each client gets its own key for tracking and revocation**
✅ **Keys are hashed and never stored in plaintext**
✅ **Works with LibreChat, Claude Desktop, MCP Inspector, and custom clients**
✅ **No rate limiting by default (as requested)**

**Next steps**: Generate your first API key and connect your clients!
