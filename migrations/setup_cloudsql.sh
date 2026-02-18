#!/bin/bash
# Setup script for Cloud SQL PostgreSQL instance

set -e  # Exit on error

echo "================================================"
echo "Google Cloud SQL PostgreSQL Setup for MCP Server"
echo "================================================"
echo ""

# Configuration
PROJECT_ID="your-gcp-project-id"  # TODO: Update this to your actual GCP project ID
REGION="us-central1" # TODO: Update this to your desired region (e.g., us-central1, us-east1, etc.)
INSTANCE_NAME="mcp-postgres"
DATABASE_NAME="customer_success"
SERVICE_NAME="customer-success-mcp"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Step 1: Create Cloud SQL Instance${NC}"
echo "This will create a PostgreSQL instance (db-f1-micro, ~$9/month)"
read -p "Continue? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Skipping instance creation..."
else
    echo "Creating Cloud SQL instance..."
    gcloud sql instances create $INSTANCE_NAME \
        --database-version=POSTGRES_15 \
        --tier=db-f1-micro \
        --region=$REGION \
        --root-password=$(openssl rand -base64 32) \
        --availability-type=zonal \
        --storage-type=SSD \
        --storage-size=10GB \
        --project=$PROJECT_ID
    
    echo -e "${GREEN}✓ Instance created${NC}"
fi

echo ""
echo -e "${YELLOW}Step 2: Create Database${NC}"
gcloud sql databases create $DATABASE_NAME \
    --instance=$INSTANCE_NAME \
    --project=$PROJECT_ID

echo -e "${GREEN}✓ Database created${NC}"

echo ""
echo -e "${YELLOW}Step 3: Get Connection Info${NC}"
CONNECTION_NAME=$(gcloud sql instances describe $INSTANCE_NAME \
    --project=$PROJECT_ID \
    --format="value(connectionName)")

echo -e "${GREEN}Connection Name: $CONNECTION_NAME${NC}"

echo ""
echo -e "${YELLOW}Step 4: Initialize Database Schema${NC}"
echo "You have two options:"
echo "1. Connect directly and paste init-db.sql"
echo "2. Upload init-db.sql to Cloud Storage and import"
echo ""
echo "Option 1 - Direct connection:"
echo "  gcloud sql connect $INSTANCE_NAME --user=postgres --project=$PROJECT_ID"
echo "  Then run: \\c $DATABASE_NAME"
echo "  Then paste contents of init-db.sql"
echo ""
echo "Option 2 - Cloud Storage import:"
echo "  1. Upload: gsutil cp init-db.sql gs://YOUR_BUCKET/"
echo "  2. Import: gcloud sql import sql $INSTANCE_NAME gs://YOUR_BUCKET/init-db.sql --database=$DATABASE_NAME"
echo ""

read -p "Press Enter to continue to Cloud Run configuration..."

echo ""
echo -e "${YELLOW}Step 5: Configure Cloud Run${NC}"
echo "Updating Cloud Run service with database connection..."

# Get current environment variables
echo "Setting environment variables..."

gcloud run services update $SERVICE_NAME \
    --region=$REGION \
    --set-env-vars="POSTGRES_HOST=/cloudsql/$CONNECTION_NAME" \
    --set-env-vars="POSTGRES_DB=$DATABASE_NAME" \
    --set-env-vars="POSTGRES_USER=postgres" \
    --add-cloudsql-instances=$CONNECTION_NAME \
    --project=$PROJECT_ID

echo -e "${GREEN}✓ Cloud Run configured${NC}"

echo ""
echo -e "${YELLOW}Step 6: Set Database Password${NC}"
echo "You need to set POSTGRES_PASSWORD as a secret or environment variable."
echo ""
echo "Using environment variable (less secure):"
echo "  gcloud run services update $SERVICE_NAME \\"
echo "    --region=$REGION \\"
echo "    --set-env-vars=\"POSTGRES_PASSWORD=YOUR_PASSWORD\" \\"
echo "    --project=$PROJECT_ID"
echo ""
echo "Or using Secret Manager (recommended):"
echo "  1. Create secret: echo -n 'YOUR_PASSWORD' | gcloud secrets create postgres-password --data-file=-"
echo "  2. Grant access: gcloud secrets add-iam-policy-binding postgres-password \\"
echo "     --member='serviceAccount:316962419897-compute@developer.gserviceaccount.com' \\"
echo "     --role='roles/secretmanager.secretAccessor'"
echo "  3. Use in Cloud Run: gcloud run services update $SERVICE_NAME \\"
echo "     --update-secrets=POSTGRES_PASSWORD=postgres-password:latest"
echo ""

echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo "Summary:"
echo "  - Instance: $INSTANCE_NAME"
echo "  - Connection: $CONNECTION_NAME"
echo "  - Database: $DATABASE_NAME"
echo ""
echo "Next steps:"
echo "  1. Initialize the database schema (see Step 4 above)"
echo "  2. Set the POSTGRES_PASSWORD (see Step 6 above)"
echo "  3. Configure AWS SES for email verification:"
echo "     gcloud run services update $SERVICE_NAME \\"
echo "       --set-env-vars='AWS_ACCESS_KEY_ID=YOUR_KEY,AWS_SECRET_ACCESS_KEY=YOUR_SECRET,AWS_REGION=us-east-1,AWS_SES_SENDER=noreply@yourdomain.com'"
echo "  4. Test registration: Use the register_user MCP tool"
echo ""
echo "Connection command (for manual DB access):"
echo "  gcloud sql connect $INSTANCE_NAME --user=postgres --project=$PROJECT_ID"
echo ""
