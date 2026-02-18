# Quick Start: User Registration System

## For Users - Register & Login

### 1. Register Account
```python
register_user(
    username="your_username",
    email="your@email.com",
    password="YourSecurePassword123",
    full_name="Your Name"  # optional
)
```

### 2. Check Email & Verify
Click the link in your email, or:
```python
verify_user_email(token="TOKEN_FROM_EMAIL")
```

### 3. Login
```python
authenticate(
    username="your_username",
    password="YourSecurePassword123"
)
# Save the access_token from response
```

### 4. Use MCP Tools
Now you can use all 25 MCP tools with your token!

---

## For Admins - Cloud SQL Setup

### One-Time Setup
```bash
# 1. Run setup script
./setup_cloudsql.sh

# 2. Initialize database
gcloud sql connect mcp-postgres --user=postgres
\c customer_success
# Paste init-db.sql contents

# 3. Set password
gcloud run services update customer-success-mcp \
  --region=us-central1 \
  --set-env-vars="POSTGRES_PASSWORD=YOUR_PASSWORD"

# 4. Deploy
gcloud builds submit --config=cloudbuild.yaml
```

### Admin Functions
```python
# List all users
list_users(admin_only=False)

# List only admins
list_users(admin_only=True)
```

---

## Troubleshooting

### "Database unavailable" 
→ Falls back to hardcoded users (admin/admin123)

### "Email not received"
→ Check AWS SES is configured:
```bash
gcloud run services update customer-success-mcp \
  --set-env-vars="AWS_ACCESS_KEY_ID=YOUR_KEY,AWS_SECRET_ACCESS_KEY=YOUR_SECRET"
```

### "Token expired"
→ Use resend:
```python
resend_verification_email(email="your@email.com")
```

---

## Cost
- **Cloud SQL**: ~$9/month (db-f1-micro)
- **Cloud Run**: Pay per use
- **Total estimate**: $10-15/month

---

## Support
- Setup Guide: [USER_REGISTRATION_SETUP.md](USER_REGISTRATION_SETUP.md)
- Implementation Details: [REGISTRATION_IMPLEMENTATION.md](REGISTRATION_IMPLEMENTATION.md)
- Database Schema: [init-db.sql](init-db.sql)
