# Troubleshooting Docker Issues

## Current Issue
Getting 500 Internal Server Error when trying to use Docker/Docker Compose.

## Quick Fix Options

### Option 1: Restart Docker Desktop (Recommended)

1. **Quit Docker Desktop completely:**
   - Click Docker icon in menu bar
   - Select "Quit Docker Desktop"
   - Wait for it to fully stop

2. **Restart Docker Desktop:**
   - Open Docker Desktop from Applications
   - Wait for "Docker Desktop is running" message

3. **Verify Docker is working:**
   ```bash
   docker ps
   ```

4. **Try again:**
   ```bash
   cd /Users/briany/Documents/csmcp
   docker-compose up -d
   ```

### Option 2: Test Without Docker (Local Development)

You can run the MCP server directly without Docker:

```bash
cd /Users/briany/Documents/csmcp

# Make sure you have a local PostgreSQL running
# Or skip database features for now

# Run the server in STDIO mode (for MCP clients)
uv run python -m src.server

# Or run as HTTP server for testing
uv run uvicorn src.server:create_sse_app --host 0.0.0.0 --port 8000 --reload
```

### Option 3: Fix Docker API Version Issues

If restarting doesn't work, the issue might be Docker API version mismatch:

```bash
# Check Docker version
docker version

# If you see API version mismatch, try:
# 1. Update Docker Desktop to latest version
# 2. Or downgrade docker-compose

# Install docker-compose v2 explicitly
brew install docker-compose

# Or use docker compose (without hyphen) - Docker's built-in compose
docker compose up -d
```

### Option 4: Remove and Reinstall Docker

If nothing else works:

```bash
# Completely remove Docker
# 1. Quit Docker Desktop
# 2. Delete Docker.app from Applications
# 3. Remove Docker data:
rm -rf ~/Library/Group\ Containers/group.com.docker
rm -rf ~/Library/Containers/com.docker.docker
rm -rf ~/.docker

# Reinstall Docker Desktop
# Download from: https://www.docker.com/products/docker-desktop
```

## Alternative: Deploy Directly to Google Cloud

Skip Docker locally and deploy straight to Google Cloud:

```bash
# Make sure gcloud is installed
brew install google-cloud-sdk

# Authenticate
gcloud auth login

# Set project
gcloud config set project YOUR_PROJECT_ID

# Enable Cloud Build
gcloud services enable cloudbuild.googleapis.com

# Deploy (Cloud Build will handle Docker for you)
gcloud builds submit --config=cloudbuild.yaml
```

## Recommended Next Steps

1. **Try Option 1 first** (restart Docker)
2. **If that fails**, use Option 2 to test locally without Docker
3. **For production**, use Option 4 to deploy to Google Cloud directly

## Testing Without Docker

Since Docker is having issues, you can test the server locally:

### 1. Set up PostgreSQL locally (optional)

```bash
# Install PostgreSQL
brew install postgresql@15

# Start PostgreSQL
brew services start postgresql@15

# Create database
createdb customer_success

# Run init script
psql customer_success < init-db.sql
```

### 2. Configure environment

```bash
# Copy example
cp .env.example .env

# Edit .env
# Set POSTGRES_HOST=localhost
# Set SMTP_HOST=localhost (or skip email features)
```

### 3. Run the server

```bash
# For MCP (STDIO)
uv run python -m src.server

# For HTTP testing
uv run uvicorn src.server:create_sse_app --host 0.0.0.0 --port 8000 --reload

# Test
curl http://localhost:8000/health
```

### 4. Run tests

```bash
# Your existing tests should still work
uv run python test_tools.py
```

## Common Docker Error Solutions

### Error: "Cannot connect to Docker daemon"
- Docker Desktop is not running
- Solution: Open Docker Desktop

### Error: "500 Internal Server Error for API route"
- API version mismatch between Docker CLI and daemon
- Solution: Restart Docker Desktop or update both

### Error: "No space left on device"
- Docker has consumed all disk space
- Solution: `docker system prune -a`

### Error: "Port already in use"
- Another service is using port 8000, 5432, etc.
- Solution: Stop the conflicting service or change ports

## Get Help

If issues persist:
1. Check Docker Desktop logs: Docker → Preferences → Troubleshoot → Show Logs
2. Reset Docker to factory defaults: Docker → Troubleshoot → Reset to factory defaults
3. Check Docker forums: https://forums.docker.com/
