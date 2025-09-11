#!/bin/bash
# deploy-cloud-run.sh
# Complete deployment script for Luna AI Server using Generative AI API

set -e

export REGION="us-central1" 
export SERVICE_NAME="luna-ai-server"
export DB_INSTANCE_NAME="luna-db-instance"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Deploying Luna AI Server to Cloud Run with FREE TIER optimization${NC}"

# Enable required APIs
echo -e "${YELLOW}📋 Enabling required APIs...${NC}"
gcloud services enable \
    run.googleapis.com \
    sql-component.googleapis.com \
    sqladmin.googleapis.com \
    cloudbuild.googleapis.com

# Create secrets if they don't exist
echo -e "${YELLOW}🔐 Creating secrets...${NC}"

# Generate JWT secret if not provided
if [ -z "$JWT_SECRET_KEY" ]; then
    export JWT_SECRET_KEY=$(openssl rand -base64 32)
fi

# Create secrets
gcloud secrets create google-api-key --data-file=<(echo -n "$GOOGLE_API_KEY") || echo "Secret already exists"
gcloud secrets create jwt-secret --data-file=<(echo -n "$JWT_SECRET_KEY") || echo "Secret already exists"
gcloud secrets create notion-token --data-file=<(echo -n "$NOTION_TOKEN") || echo "Secret already exists"
gcloud secrets create db-password --data-file=<(echo -n "$DB_PASSWORD") || echo "Secret already exists"
gcloud secrets create browserbase-api-key --data-file=<(echo -n "$BROWSERBASE_API_KEY") || echo "Secret already exists"

# Create PostgreSQL instance with MINIMAL configuration for alpha testing
echo -e "${YELLOW}🗄️  Creating minimal Cloud SQL instance for alpha...${NC}"
gcloud sql instances create $DB_INSTANCE_NAME \
    --database-version=POSTGRES_15 \
    --tier=db-f1-micro \
    --region=$REGION \
    --storage-type=HDD \
    --storage-size=10GB \
    --no-storage-auto-increase \
    --no-backup \
    --maintenance-window-day=SUN \
    --maintenance-window-hour=4 \
    --authorized-networks=0.0.0.0/0 \
    --deletion-protection=false || echo "Database instance already exists"

# Create database and user
gcloud sql databases create luna_db --instance=$DB_INSTANCE_NAME || echo "Database already exists"
gcloud sql users create luna_user --instance=$DB_INSTANCE_NAME --password="$DB_PASSWORD" || echo "User already exists"

# Get Cloud SQL connection name
export DB_CONNECTION_NAME=$(gcloud sql instances describe $DB_INSTANCE_NAME --format="value(connectionName)")

echo -e "${YELLOW}🐳 Building and deploying to Cloud Run with BUDGET OPTIMIZATION...${NC}"

# Deploy to Cloud Run with minimal resource allocation
gcloud run deploy $SERVICE_NAME \
    --source . \
    --dockerfile Dockerfile.cloud \
    --platform managed \
    --region $REGION \
    --project $PROJECT_ID \
    --add-cloudsql-instances $DB_CONNECTION_NAME \
    --set-env-vars GOOGLE_GENAI_USE_VERTEXAI=false \
    --set-env-vars HOST=0.0.0.0 \
    --set-env-vars PORT=8080 \
    --set-env-vars DB_HOST="/cloudsql/$DB_CONNECTION_NAME" \
    --set-env-vars DB_PORT=5432 \
    --set-env-vars DB_NAME=luna_db \
    --set-env-vars DB_USER=luna_user \
    --set-env-vars DB_ECHO=false \
    --set-env-vars NOTION_DATABASE_ID=257e6d1790a580728a5cce7a6dc24468 \
    --set-env-vars BROWSERBASE_PROJECT_ID=07dff6cd-7f2e-429c-bd5e-6c113eeb0aa1 \
    --set-env-vars PYTHONDONTWRITEBYTECODE=1 \
    --set-env-vars PYTHONUNBUFFERED=1 \
    --set-secrets GOOGLE_API_KEY=google-api-key:latest \
    --set-secrets JWT_SECRET_KEY=jwt-secret:latest \
    --set-secrets NOTION_TOKEN=notion-token:latest \
    --set-secrets DB_PASSWORD=db-password:latest \
    --set-secrets BROWSERBASE_API_KEY=browserbase-api-key:latest \
    --memory 1Gi \
    --cpu 1 \
    --timeout 3600 \
    --concurrency 80 \
    --min-instances 0 \
    --max-instances 3 \
    --cpu-throttling \
    --allow-unauthenticated

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")

echo -e "${GREEN}✅ Deployment complete!${NC}"
echo -e "${GREEN}🌐 Service URL: $SERVICE_URL${NC}"
echo -e "${GREEN}🏥 Health check: $SERVICE_URL/health${NC}"
echo -e "${GREEN}📊 Metrics: $SERVICE_URL/metrics${NC}"

# Test the deployment
echo -e "${YELLOW}🧪 Testing deployment...${NC}"
if curl -f "$SERVICE_URL/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Health check passed!${NC}"
else
    echo -e "${RED}❌ Health check failed!${NC}"
    echo -e "${YELLOW}Check logs: gcloud run logs tail $SERVICE_NAME --region=$REGION${NC}"
fi
