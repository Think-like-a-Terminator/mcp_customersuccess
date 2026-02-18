# 🚀 Quick Deployment Guide

## Prerequisites

Before deploying, you need:

### For Local Docker Testing:
- **Docker Desktop**: https://www.docker.com/products/docker-desktop
- **Docker Compose** (included with Docker Desktop)

### For Google Cloud Deployment:
- **Google Cloud SDK**: https://cloud.google.com/sdk/docs/install
- **GCP Project** with billing enabled
- **Docker** (to test locally before deploying)

---

## Option 1: Local Docker Testing

### Using Docker Compose (Recommended)

```bash
# Start all services (MCP server and PostgreSQL)
docker-compose up -d

# View logs
docker-compose logs -f mcp-server

# Access services
# - MCP Server: http://localhost:8000
# - MCP Health Check: http://localhost:8000/health
# - PostgreSQL: localhost:5432

# Stop services
docker-compose down
```

### Using Docker Only

```bash
# Build image
docker build -t customer-success-mcp .

# Run container
docker run -p 8000:8000 \
  -e POSTGRES_HOST=your-db-host \
  -e POSTGRES_PASSWORD=your-password \
  customer-success-mcp
```

---

## Option 2: Google Cloud Run (Production)

### One-Command Deployment

```bash
./deploy.sh
# Choose option 3 and enter your GCP project ID
```

### Manual Step-by-Step

1. **Install Google Cloud SDK** (if not installed):
```bash
# macOS
brew install google-cloud-sdk

# Or download from:
# https://cloud.google.com/sdk/docs/install
```

2. **Authenticate and set project**:
```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

3. **Enable required APIs**:
```bash
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable sql-component.googleapis.com
```

4. **Create Cloud SQL instance** (PostgreSQL):
```bash
# Create instance
gcloud sql instances create mcp-postgres \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1

# Create database
gcloud sql databases create customer_success \
  --instance=mcp-postgres

# Set password
gcloud sql users set-password postgres \
  --instance=mcp-postgres \
  --password=YOUR_SECURE_PASSWORD
```

5. **Deploy application**:
```bash
gcloud builds submit --config=cloudbuild.yaml
```

6. **Get your service URL**:
```bash
gcloud run services describe customer-success-mcp \
  --region=us-central1 \
  --format='value(status.url)'
```

---

## Option 3: Deploy Script

Use the interactive deployment script:

```bash
./deploy.sh
```

Options:
1. Build Docker image locally
2. Run with Docker Compose
3. Deploy to Google Cloud Run
4. Exit

---

## Configuration

### Environment Variables

Create `.env` file (copy from `.env.example`):

```bash
# Authentication
JWT_SECRET_KEY=your-very-secure-secret-key

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=customer_success
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-password

# SMTP (Optional, for email verification and survey emails)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=reports@example.com

# AWS SES (Optional, for email verification and survey emails)
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_REGION=us-east-1
AWS_SES_SENDER=noreply@yourdomain.com
```

### For Google Cloud Run

Set environment variables:
```bash
gcloud run services update customer-success-mcp \
  --region=us-central1 \
  --set-env-vars="JWT_SECRET_KEY=your-secret" \
  --set-env-vars="POSTGRES_HOST=/cloudsql/PROJECT:REGION:INSTANCE" \
  --set-env-vars="POSTGRES_PASSWORD=your-db-password" \
  --set-env-vars="AWS_ACCESS_KEY_ID=your-aws-key" \
  --set-env-vars="AWS_SECRET_ACCESS_KEY=your-aws-secret" \
  --set-env-vars="AWS_REGION=us-east-1" \
  --set-env-vars="AWS_SES_SENDER=noreply@yourdomain.com" \
  --set-env-vars="SMTP_HOST=smtp.gmail.com" \
  --set-env-vars="SMTP_PORT=587" \
  --set-env-vars="SMTP_USERNAME=your-email@gmail.com" \
  --set-env-vars="SMTP_PASSWORD=your-gmail-app-password"
```

Or use Secret Manager:
```bash
# Create secret
echo -n "your-jwt-secret" | gcloud secrets create jwt-secret-key --data-file=-

# Use in Cloud Run
gcloud run services update customer-success-mcp \
  --region=us-central1 \
  --set-secrets="JWT_SECRET_KEY=jwt-secret-key:latest"
```

---

## Testing Deployment

### Health Check

```bash
# Local
curl http://localhost:8000/health

# Cloud Run
curl https://your-service-url/health
```

### Test Authentication

```bash
# Local
curl -X POST http://localhost:8000/messages \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "authenticate",
      "arguments": {
        "username": "admin",
        "password": "admin123"
      }
    }
  }'

# Or test with MCP client (see README.md for Claude Desktop setup)
```

---

## Monitoring

### View Logs

**Docker:**
```bash
docker-compose logs -f mcp-server
```

**Cloud Run:**
```bash
gcloud run services logs read customer-success-mcp \
  --region=us-central1 \
  --limit=50
```

### Metrics

Access Cloud Run metrics:
```
https://console.cloud.google.com/run/detail/us-central1/customer-success-mcp/metrics
```

---

## Costs

### Cloud Run Pricing
- First 2 million requests/month: **FREE**
- After: $0.40 per million requests
- CPU: $0.00002400 per vCPU-second
- Memory: $0.00000250 per GiB-second

### Cloud SQL (db-f1-micro)
- ~$15/month for smallest instance

### Estimated Monthly Cost
- Light usage: **$15-25/month**
- Medium usage (10K requests/day): **$20-35/month**
- Heavy usage (100K requests/day): **$30-50/month**

---

## Troubleshooting

### Docker build fails
```bash
# Clear Docker cache
docker system prune -a

# Rebuild
docker build --no-cache -t customer-success-mcp .
```

### Can't connect to database
```bash
# Check connection string
echo $POSTGRES_HOST

# Test database connection
docker-compose exec postgres psql -U postgres -d customer_success
```

### Cloud Run deployment fails
```bash
# Check build logs
gcloud builds log $(gcloud builds list --limit=1 --format='value(ID)')

# Check service status
gcloud run services describe customer-success-mcp --region=us-central1
```

---

## Next Steps

1. ✅ Deploy locally with Docker Compose
2. ✅ Test health check endpoint
3. ✅ Set up Cloud SQL on GCP (see [USER_REGISTRATION_SETUP.md](USER_REGISTRATION_SETUP.md))
4. ✅ Configure AWS SES for email verification
5. ✅ Configure SMTP for ROI reports
6. ✅ Deploy to Cloud Run
7. ⬜ Test user registration flow
8. ⬜ Configure custom domain
9. ⬜ Set up monitoring and alerts
10. ⬜ Set up CI/CD pipeline

---

## Support

For detailed deployment instructions, see:
- [DEPLOYMENT.md](DEPLOYMENT.md) - Complete deployment guide
- [README.md](README.md) - Main project documentation
- [USER_REGISTRATION_SETUP.md](USER_REGISTRATION_SETUP.md) - User registration system setup
- [ROI_REPORT_TOOL.md](ROI_REPORT_TOOL.md) - ROI report configuration

For issues:
1. Check logs: `docker-compose logs -f` or `gcloud run services logs read`
2. Verify environment variables are set
3. Test database connectivity
4. Check AWS SES sender is verified
5. Review Cloud Run logs for errors

---

## Security Checklist

Before going to production:

- [ ] Change default JWT_SECRET_KEY (use strong random value)
- [ ] Change default admin password (admin/admin123)
- [ ] Use strong database passwords
- [ ] Enable Cloud SQL SSL connections
- [ ] Use Secret Manager for sensitive data (JWT secret, DB password, AWS keys)
- [ ] Verify AWS SES sender email/domain
- [ ] Configure SMTP with app-specific password (not regular password)
- [ ] Configure IAM permissions properly
- [ ] Enable Cloud Armor for DDoS protection (optional)
- [ ] Set up VPC connector for private networking (optional)
- [ ] Enable audit logging
- [ ] Configure backup strategy for Cloud SQL
- [ ] Set up monitoring and alerting
- [ ] Test email verification flow end-to-end

---

## Resources

- **Docker Hub**: https://hub.docker.com/
- **Google Cloud Console**: https://console.cloud.google.com
- **Cloud Run Docs**: https://cloud.google.com/run/docs
- **Cloud SQL Docs**: https://cloud.google.com/sql/docs
