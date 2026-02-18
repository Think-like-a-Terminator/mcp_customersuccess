# User Registration System Setup Guide

## Overview

The Customer Success MCP Server now includes a complete user registration system with:
- ✅ Self-service user registration
- ✅ Email verification via AWS SES
- ✅ PostgreSQL database storage
- ✅ Backward compatibility with hardcoded users
- ✅ Admin user management tools

## Architecture

### New Components

1. **users table** in PostgreSQL (see [init-db.sql](init-db.sql))
2. **UserService** ([src/user_service.py](src/user_service.py)) - Handles registration, verification
3. **Updated auth.py** - Checks database first, falls back to hardcoded users
4. **4 new MCP tools** - `register_user`, `verify_user_email`, `resend_verification_email`, `list_users`

## Setup Instructions

### Step 1: Create Cloud SQL PostgreSQL Instance

```bash
# Create a PostgreSQL instance in Google Cloud
gcloud sql instances create mcp-postgres \
    --database-version=POSTGRES_15 \
    --tier=db-f1-micro \
    --region=us-central1 \
    --root-password=YOUR_SECURE_PASSWORD \
    --availability-type=zonal \
    --storage-type=SSD \
    --storage-size=10GB

# Create the database
gcloud sql databases create customer_success \
    --instance=mcp-postgres

# Get the connection name
gcloud sql instances describe mcp-postgres --format="value(connectionName)"
# Output: gen-lang-client-0335658587:us-central1:mcp-postgres
```

### Step 2: Initialize Database Schema

```bash
# Connect to Cloud SQL and run init-db.sql
gcloud sql connect mcp-postgres --user=postgres

# At the postgres prompt:
\c customer_success

# Copy and paste the contents of init-db.sql or:
# Upload init-db.sql to Cloud Storage, then:
gcloud sql import sql mcp-postgres gs://YOUR_BUCKET/init-db.sql \
    --database=customer_success
```

### Step 3: Configure Cloud Run Environment Variables

```bash
# Update Cloud Run service with database connection info
gcloud run services update customer-success-mcp \
    --region=us-central1 \
    --set-env-vars="POSTGRES_HOST=/cloudsql/gen-lang-client-0335658587:us-central1:mcp-postgres" \
    --set-env-vars="POSTGRES_DB=customer_success" \
    --set-env-vars="POSTGRES_USER=postgres" \
    --set-env-vars="POSTGRES_PASSWORD=YOUR_SECURE_PASSWORD" \
    --add-cloudsql-instances=gen-lang-client-0335658587:us-central1:mcp-postgres

# Configure AWS SES for email verification (if not already set)
gcloud run services update customer-success-mcp \
    --region=us-central1 \
    --set-env-vars="AWS_ACCESS_KEY_ID=YOUR_AWS_KEY" \
    --set-env-vars="AWS_SECRET_ACCESS_KEY=YOUR_AWS_SECRET" \
    --set-env-vars="AWS_REGION=us-east-1" \
    --set-env-vars="AWS_SES_SENDER=noreply@yourdomain.com"
```

### Step 4: Update docker-compose.yml for Local Testing

The [docker-compose.yml](docker-compose.yml) already includes PostgreSQL. Just ensure it's running:

```bash
docker-compose up -d postgres

# Run database initialization
docker-compose exec postgres psql -U postgres -d customer_success -f /docker-entrypoint-initdb.d/init-db.sql
```

## Usage

### For New Users

#### 1. Register an Account

```python
# Using the MCP tool
register_user(
    username="john_doe",
    email="john@example.com",
    password="SecurePass123!",
    full_name="John Doe"
)

# Response:
{
    "success": true,
    "id": 1,
    "username": "john_doe",
    "email": "john@example.com",
    "email_verified": false,
    "message": "Registration successful! Please check your email to verify your account."
}
```

#### 2. Verify Email

User receives an email with a verification link:
```
https://your-mcp-server-url.run.app/verify?token=ABC123XYZ...
```

Or use the MCP tool directly:
```python
verify_user_email(token="ABC123XYZ...")

# Response:
{
    "success": true,
    "message": "Email verified successfully!",
    "username": "john_doe"
}
```

#### 3. Login

```python
authenticate(username="john_doe", password="SecurePass123!")

# Response:
{
    "success": true,
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "token_type": "bearer",
    "user": {
        "username": "john_doe",
        "email": "john@example.com",
        "email_verified": true,
        "scopes": ["read", "write"]
    }
}
```

### For Admins

#### List All Users

```python
list_users(admin_only=False)

# Response:
{
    "success": true,
    "count": 3,
    "users": [
        {
            "id": 1,
            "username": "admin",
            "email": "admin@example.com",
            "email_verified": true,
            "scopes": ["read", "write", "admin"]
        },
        {
            "id": 2,
            "username": "john_doe",
            "email": "john@example.com",
            "email_verified": true,
            "scopes": ["read", "write"]
        }
    ]
}
```

## Security Features

### Password Requirements
- ✅ Minimum 8 characters
- ✅ Bcrypt hashing with salt
- ✅ No password storage in logs or responses

### Email Verification
- ✅ Secure tokens (32 bytes, URL-safe)
- ✅ 24-hour expiration
- ✅ One-time use tokens
- ✅ Resend capability

### Scopes/Permissions
- **read**: View data
- **write**: Create/update data
- **admin**: User management, system admin

### Fallback Authentication
If PostgreSQL is unavailable, the system automatically falls back to hardcoded users:
- `admin` / `admin123` (admin scope)
- `csm` / `csm123` (read/write scope)

## Database Schema

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255),
    hashed_password TEXT NOT NULL,
    disabled BOOLEAN DEFAULT FALSE,
    scopes TEXT[] DEFAULT ARRAY['read', 'write'],
    email_verified BOOLEAN DEFAULT FALSE,
    verification_token VARCHAR(255),
    verification_token_expires TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Troubleshooting

### Issue: "Database unavailable"
- Check Cloud SQL instance is running: `gcloud sql instances list`
- Verify Cloud Run has Cloud SQL connection configured
- Check environment variables are set correctly

### Issue: "Email not received"
- Verify AWS SES is configured and verified
- Check sender email is verified in AWS SES
- Look at Cloud Run logs for email sending errors

### Issue: "Username already taken"
- Usernames must be unique across all users
- Try a different username or check if you already have an account

### Issue: "Verification token expired"
- Tokens expire after 24 hours
- Use `resend_verification_email` to get a new token

## Cost Estimates

### Cloud SQL (db-f1-micro)
- **Compute**: ~$7.67/month
- **Storage**: 10GB SSD ~$1.70/month
- **Total**: ~$9.37/month

### Optimization Options
1. **Use Cloud SQL Proxy** for secure connections
2. **Enable automated backups** (additional cost)
3. **Scale up** to db-g1-small for production (~$25/month)

## Next Steps

1. ✅ Set up Cloud SQL instance
2. ✅ Configure environment variables in Cloud Run
3. ✅ Test registration locally with docker-compose
4. ✅ Deploy to Cloud Run with database connection
5. ⬜ Set up custom domain for verification emails
6. ⬜ Add password reset functionality
7. ⬜ Implement rate limiting on registration
8. ⬜ Add user profile management tools

## API Reference

### New MCP Tools

| Tool | Description | Auth Required |
|------|-------------|---------------|
| `register_user` | Create new user account | No |
| `verify_user_email` | Verify email with token | No |
| `resend_verification_email` | Request new verification email | No |
| `list_users` | List all users (admin) | Yes (admin) |

### Existing Tools Enhanced
- `authenticate` - Now checks PostgreSQL database first
