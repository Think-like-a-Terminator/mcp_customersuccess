# Deployment Guide - Docker & Google Cloud

This guide covers deploying the Customer Success MCP Server using Docker and Google Cloud Platform.

## Table of Contents
- [Local Docker Deployment](#local-docker-deployment)
- [Google Cloud Run Deployment](#google-cloud-run-deployment)
- [Google Kubernetes Engine (GKE) Deployment](#gke-deployment)
- [Configuration](#configuration)
- [Monitoring](#monitoring)

---

## Local Docker Deployment

### Prerequisites
- Docker Desktop installed
- Docker Compose installed

### Quick Start

1. **Build and run with Docker Compose:**
```bash
docker-compose up -d
```

This starts:
- MCP Server (port 8000)
- PostgreSQL database (port 5432)
- MailHog for email testing (SMTP: 1025, Web UI: 8025)

2. **View logs:**
```bash
docker-compose logs -f mcp-server
```

3. **Test the server:**
```bash
curl http://localhost:8000/health
```

4. **Access MailHog UI:**
```
http://localhost:8025
```

5. **Stop services:**
```bash
docker-compose down
```

### Build Docker Image Only

```bash
# Build the image
docker build -t customer-success-mcp:latest .

# Run the container
docker run -p 8000:8000 \
  -e POSTGRES_HOST=host.docker.internal \
  -e POSTGRES_PASSWORD=yourpassword \
  customer-success-mcp:latest
```

### Environment Variables

Create a `.env` file:
```bash
# Authentication
JWT_SECRET_KEY=your-secure-secret-key

# PostgreSQL
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=customer_success
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-password

# SMTP
SMTP_HOST=mailhog
SMTP_PORT=1025
SMTP_FROM_EMAIL=reports@example.com

# AWS (optional)
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
```

---

## Google Cloud Run Deployment

### Prerequisites
- Google Cloud SDK (`gcloud`) installed
- Google Cloud project created
- Billing enabled on the project

### Setup

1. **Authenticate with Google Cloud:**
```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

2. **Enable required APIs:**
```bash
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable sql-component.googleapis.com
gcloud services enable sqladmin.googleapis.com
```

3. **Set up Cloud SQL (PostgreSQL):**
```bash
# Create Cloud SQL instance
gcloud sql instances create mcp-postgres \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1

# Create database
gcloud sql databases create customer_success \
  --instance=mcp-postgres

# Set root password
gcloud sql users set-password postgres \
  --instance=mcp-postgres \
  --password=YOUR_SECURE_PASSWORD
```

4. **Create secrets in Secret Manager:**
```bash
# Enable Secret Manager API
gcloud services enable secretmanager.googleapis.com

# Create secrets
echo -n "your-jwt-secret" | gcloud secrets create jwt-secret-key --data-file=-
echo -n "your-db-password" | gcloud secrets create postgres-password --data-file=-
```

### Deploy with Cloud Build

1. **Build and deploy automatically:**
```bash
gcloud builds submit --config=cloudbuild.yaml
```

This will:
- Build the Docker image
- Push to Google Container Registry
- Deploy to Cloud Run

2. **Configure environment variables:**
```bash
gcloud run services update customer-success-mcp \
  --region=us-central1 \
  --set-env-vars="JWT_SECRET_KEY=$(gcloud secrets versions access latest --secret=jwt-secret-key)" \
  --set-env-vars="POSTGRES_HOST=/cloudsql/YOUR_PROJECT_ID:us-central1:mcp-postgres" \
  --set-env-vars="POSTGRES_DB=customer_success" \
  --set-env-vars="POSTGRES_USER=postgres" \
  --set-env-vars="POSTGRES_PASSWORD=$(gcloud secrets versions access latest --secret=postgres-password)"
```

3. **Connect Cloud Run to Cloud SQL:**
```bash
gcloud run services update customer-success-mcp \
  --region=us-central1 \
  --add-cloudsql-instances=YOUR_PROJECT_ID:us-central1:mcp-postgres
```

### Manual Deploy

```bash
# Build and push image
docker build -t gcr.io/YOUR_PROJECT_ID/customer-success-mcp:latest .
docker push gcr.io/YOUR_PROJECT_ID/customer-success-mcp:latest

# Deploy to Cloud Run
gcloud run deploy customer-success-mcp \
  --image=gcr.io/YOUR_PROJECT_ID/customer-success-mcp:latest \
  --platform=managed \
  --region=us-central1 \
  --allow-unauthenticated \
  --memory=1Gi \
  --cpu=1 \
  --timeout=300 \
  --max-instances=10
```

### Get Service URL

```bash
gcloud run services describe customer-success-mcp \
  --region=us-central1 \
  --format='value(status.url)'
```

---

## GKE Deployment (Kubernetes)

### Prerequisites
- GKE cluster created
- `kubectl` configured

### Deploy to GKE

1. **Create Kubernetes manifests:**

`k8s/deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: customer-success-mcp
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mcp-server
  template:
    metadata:
      labels:
        app: mcp-server
    spec:
      containers:
      - name: mcp-server
        image: gcr.io/YOUR_PROJECT_ID/customer-success-mcp:latest
        ports:
        - containerPort: 8000
        env:
        - name: POSTGRES_HOST
          value: postgres-service
        envFrom:
        - secretRef:
            name: mcp-secrets
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
```

2. **Deploy:**
```bash
kubectl apply -f k8s/
```

---

## Configuration

### Health Check Endpoint

The server includes a health check at `/health`:
```bash
curl https://your-service-url/health
```

### Scaling Configuration

**Cloud Run:**
```bash
gcloud run services update customer-success-mcp \
  --min-instances=1 \
  --max-instances=10 \
  --concurrency=80
```

**GKE:**
```bash
kubectl autoscale deployment customer-success-mcp \
  --cpu-percent=70 \
  --min=2 \
  --max=10
```

### Custom Domain

**Cloud Run:**
```bash
gcloud run domain-mappings create \
  --service=customer-success-mcp \
  --domain=mcp.yourdomain.com \
  --region=us-central1
```

---

## Monitoring

### Cloud Run Logs

```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=customer-success-mcp" \
  --limit=50 \
  --format=json
```

### Metrics

View in Cloud Console:
```
https://console.cloud.google.com/run/detail/us-central1/customer-success-mcp/metrics
```

### Alerts

Set up alerting for:
- Error rate > 5%
- Response time > 2s
- Memory usage > 80%

---

## Cost Optimization

### Cloud Run Pricing
- Pay per request
- First 2 million requests free per month
- CPU charged only during request handling

### Recommendations
1. Use `--min-instances=0` for development
2. Use `--min-instances=1` for production (avoid cold starts)
3. Set appropriate `--max-instances` to control costs
4. Use Cloud SQL auth proxy for secure connections
5. Enable Cloud CDN for static assets

---

## Security Best Practices

1. **Use Secret Manager:**
   - Store all sensitive credentials in Secret Manager
   - Never commit secrets to git

2. **IAM Permissions:**
   ```bash
   # Grant Cloud SQL access
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member=serviceAccount:YOUR_SERVICE_ACCOUNT \
     --role=roles/cloudsql.client
   ```

3. **Network Security:**
   - Use VPC connector for private database access
   - Enable Cloud Armor for DDoS protection

4. **Authentication:**
   - Use Cloud Identity-Aware Proxy (IAP) for additional auth layer
   - Implement API keys for external access

---

## Troubleshooting

### Container won't start
```bash
# View logs
docker logs customer-success-mcp

# Check Cloud Run logs
gcloud run services logs read customer-success-mcp --region=us-central1
```

### Database connection issues
```bash
# Test Cloud SQL connection
gcloud sql connect mcp-postgres --user=postgres

# Check network connectivity
gcloud run services describe customer-success-mcp --region=us-central1
```

### Performance issues
```bash
# Increase resources
gcloud run services update customer-success-mcp \
  --memory=2Gi \
  --cpu=2
```

---

## CI/CD Pipeline

### GitHub Actions Example

`.github/workflows/deploy.yml`:
```yaml
name: Deploy to Google Cloud Run

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - id: auth
        uses: google-github-actions/auth@v1
        with:
          credentials_json: ${{ secrets.GCP_CREDENTIALS }}
      
      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v1
      
      - name: Build and Deploy
        run: |
          gcloud builds submit --config=cloudbuild.yaml
```

---

## Post-Deployment: API Key Setup

After deploying, you need to set up API key authentication for secure multi-client access.

### Step 1: Generate Bootstrap Admin API Key

The first API key must be created with `created_by='admin'` to enable key management.

**Option A: Use the bootstrap script (recommended)**
```bash
python bootstrap_admin_key.py
```

**Option B: Manual generation**
```bash
python -c "
from src.api_key_service import APIKeyService
service = APIKeyService()
result = service.create_api_key(
    name='Bootstrap Admin Key',
    description='Initial admin key for key management',
    created_by='admin'
)
print(f'Admin API Key: {result[\"api_key\"]}')
"
```

⚠️ **Save this key securely!** You need it to generate additional API keys.

### Step 2: Test Admin Key

```bash
# Test with your new admin key
python test_cloud_api_key.py csm_live_YourAdminKeyHere
```

### Step 3: Generate Client API Keys

Use MCP Inspector or Claude Desktop with your admin key to generate keys for clients:

```bash
# Launch MCP Inspector with admin key
npx @modelcontextprotocol/inspector sse \
  https://customer-success-mcp-316962419897.us-central1.run.app/sse \
  --header "X-API-Key: csm_live_YourAdminKeyHere"

# Then use the generate_api_key tool
```

Or directly from Python (requires database access):
```python
from src.api_key_service import APIKeyService
service = APIKeyService()

# Note: Only works locally, use MCP tools for cloud deployment
result = service.create_api_key(
    name="LibreChat Production",
    description="Key for LibreChat client",
    created_by="admin"
)
print(result["api_key"])
```

### Step 4: Configure Clients

Add the API key to your client configurations:

**LibreChat:**
```yaml
MCP_SERVERS: |
  {
    "customer-success": {
      "url": "https://customer-success-mcp-316962419897.us-central1.run.app",
      "transport": "sse",
      "headers": {
        "X-API-Key": "csm_live_YourClientKeyHere"
      }
    }
  }
```

**Note**: Use a separate client API key (not your admin key) for LibreChat.

**Claude Desktop:**
```json
{
  "mcpServers": {
    "customer-success": {
      "url": "https://customer-success-mcp-316962419897.us-central1.run.app",
      "transport": "sse",
      "headers": {
        "X-API-Key": "csm_live_YourClientKeyHere"
      }
    }
  }
}
```

### Step 5: Test API Key Authentication

```bash
# Test without API key (should fail with 401)
curl https://customer-success-mcp-316962419897.us-central1.run.app/sse

# Test with valid API key (should succeed)
curl -H "X-API-Key: csm_live_YourAPIKeyHere" \
     https://customer-success-mcp-316962419897.us-central1.run.app/sse

# Or use the automated test script
python test_cloud_api_key.py csm_live_YourAPIKeyHere
```

For detailed API key setup, see **[API_KEY_SETUP.md](API_KEY_SETUP.md)**.

---

## Next Steps

1. **Set up API key authentication** (see above)
2. Set up monitoring and alerting
3. Configure custom domain
4. Set up CI/CD pipeline
5. Configure backup strategy for Cloud SQL
6. Set up Cloud CDN
7. Implement user registration and verification

For more information, see:
- [API Key Setup Guide](API_KEY_SETUP.md)
