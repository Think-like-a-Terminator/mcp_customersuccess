#!/bin/bash

# Quick Start Script for Customer Success MCP Server Deployment

set -e

echo "========================================"
echo "Customer Success MCP Server Deployment"
echo "========================================"
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo "Checking prerequisites..."

if ! command_exists docker; then
    echo "❌ Docker is not installed"
    echo "   Install from: https://www.docker.com/products/docker-desktop"
    exit 1
fi

if ! command_exists docker-compose; then
    echo "⚠️  Docker Compose is not installed (optional for local testing)"
fi

if ! command_exists gcloud; then
    echo "⚠️  Google Cloud SDK is not installed (required for GCP deployment)"
    echo "   Install from: https://cloud.google.com/sdk/docs/install"
fi

echo "✅ Docker is installed"
echo ""

# Menu
echo "Choose deployment option:"
echo "1) Build Docker image locally"
echo "2) Run with Docker Compose (local testing)"
echo "3) Deploy to Google Cloud Run"
echo "4) Exit"
echo ""
read -p "Enter choice [1-4]: " choice

case $choice in
    1)
        echo ""
        echo "Building Docker image..."
        docker build -t customer-success-mcp:latest .
        echo ""
        echo "✅ Image built successfully!"
        echo "Run with: docker run -p 8000:8000 customer-success-mcp:latest"
        ;;
    
    2)
        echo ""
        if ! command_exists docker-compose; then
            echo "❌ Docker Compose is required for this option"
            exit 1
        fi
        echo "Starting services with Docker Compose..."
        docker-compose up -d
        echo ""
        echo "✅ Services started!"
        echo "   MCP Server: http://localhost:8000"
        echo "   MailHog UI: http://localhost:8025"
        echo "   PostgreSQL: localhost:5432"
        echo ""
        echo "View logs: docker-compose logs -f"
        echo "Stop services: docker-compose down"
        ;;
    
    3)
        echo ""
        if ! command_exists gcloud; then
            echo "❌ Google Cloud SDK is required for this option"
            exit 1
        fi
        
        read -p "Enter your GCP Project ID: " project_id
        
        if [ -z "$project_id" ]; then
            echo "❌ Project ID is required"
            exit 1
        fi
        
        echo "Setting GCP project..."
        gcloud config set project "$project_id"
        
        echo "Building and deploying to Cloud Run..."
        gcloud builds submit --config=cloudbuild.yaml
        
        echo ""
        echo "✅ Deployment complete!"
        echo "Get service URL:"
        echo "  gcloud run services describe customer-success-mcp --region=us-central1 --format='value(status.url)'"
        ;;
    
    4)
        echo "Exiting..."
        exit 0
        ;;
    
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "Done!"
