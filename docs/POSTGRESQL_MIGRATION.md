# PostgreSQL Storage Migration Guide

## Overview

The Customer Success MCP Server now uses **PostgreSQL** as the backend storage for all tool data, replacing the previous in-memory storage. This provides:

✅ **Data Persistence** - Data survives server restarts  
✅ **Scalability** - Handle large datasets efficiently  
✅ **Analytics** - Direct SQL queries for reporting  
✅ **Production Ready** - Enterprise-grade reliability  
✅ **Cloud Native** - Works with Cloud SQL, RDS, etc.  

## What Changed

### Before: In-Memory Storage
- Data stored in Python dictionaries
- Lost on server restart
- Not suitable for production
- Limited to single server instance

### After: PostgreSQL Storage
- Data persisted in PostgreSQL tables
- Survives restarts and redeployments
- Production-ready and scalable
- Supports horizontal scaling with read replicas

## Database Schema

### New Tables

#### 1. `call_to_actions`
Stores Call to Actions for customer accounts.

```sql
CREATE TABLE call_to_actions (
    id UUID PRIMARY KEY,
    account_id VARCHAR(100) NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    priority VARCHAR(20),  -- low, medium, high, urgent
    status VARCHAR(20),    -- open, in_progress, completed, cancelled
    owner VARCHAR(255),
    due_date TIMESTAMP,
    completed_at TIMESTAMP,
    tags TEXT[],
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

#### 2. `health_scores`
Stores account health scores with metrics.

```sql
CREATE TABLE health_scores (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(100) UNIQUE NOT NULL,
    overall_score DECIMAL(5,2),
    status VARCHAR(20),  -- excellent, good, at_risk, critical
    metrics JSONB,       -- Array of metric objects
    trend VARCHAR(20),   -- improving, declining, stable
    last_calculated TIMESTAMP,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

#### 3. `surveys`
Stores survey/NPS delivery records.

```sql
CREATE TABLE surveys (
    id UUID PRIMARY KEY,
    survey_id VARCHAR(100) UNIQUE NOT NULL,
    account_id VARCHAR(100) NOT NULL,
    survey_type VARCHAR(20),  -- nps, csat, custom
    recipient_email VARCHAR(255),
    subject VARCHAR(500),
    sent_at TIMESTAMP,
    response_received BOOLEAN,
    response_score INTEGER,
    response_feedback TEXT,
    response_at TIMESTAMP
);
```

#### 4. `risk_alerts`
Stores risk alerts for accounts.

```sql
CREATE TABLE risk_alerts (
    id UUID PRIMARY KEY,
    account_id VARCHAR(100) NOT NULL,
    risk_level VARCHAR(20),  -- none, low, medium, high
    risk_factors TEXT[],
    impact_score DECIMAL(5,2),
    recommended_actions TEXT[],
    acknowledged BOOLEAN,
    acknowledged_by VARCHAR(255),
    acknowledged_at TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

## Migration Steps

### Step 1: Ensure PostgreSQL is Running

**Local Development:**
```bash
# Install PostgreSQL (macOS)
brew install postgresql@14
brew services start postgresql@14

# Install PostgreSQL (Ubuntu/Debian)
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql

# Create database
createdb customer_success
```

**Google Cloud SQL:**
```bash
# Create Cloud SQL instance
gcloud sql instances create customer-success-db \
    --database-version=POSTGRES_14 \
    --tier=db-f1-micro \
    --region=us-central1

# Create database
gcloud sql databases create customer_success \
    --instance=customer-success-db
```

### Step 2: Configure Database Connection

Update `.env` file with PostgreSQL credentials:

```bash
# PostgreSQL Configuration (required)
DB_HOST=localhost          # Or Cloud SQL host
DB_PORT=5432
DB_NAME=customer_success
DB_USER=postgres           # Or your database user
DB_PASSWORD=your_password
```

**For Cloud SQL with Cloud Run:**
```bash
DB_HOST=/cloudsql/project-id:region:instance-name  # Unix socket
DB_PORT=5432
DB_NAME=customer_success
DB_USER=postgres
DB_PASSWORD=your_password
```

### Step 3: Run Database Migration

Use the migration script to create tables:

```bash
python migrate_to_postgresql.py
```

Or manually run the SQL:

```bash
psql -d customer_success -f init-db.sql
```

**Expected output:**
```
✅ Connected to PostgreSQL
✅ Tables created/updated successfully
✅ Found 7 tables:
   • api_keys
   • call_to_actions
   • customers
   • health_scores
   • risk_alerts
   • surveys
   • users
```

### Step 4: Restart MCP Server

```bash
# Local development
python -m src.server

# Docker
docker-compose restart mcp-server

# Cloud Run
gcloud builds submit --config=cloudbuild.yaml
```

### Step 5: Verify Data Persistence

Test that data persists across restarts:

```bash
# 1. Create a CTA via MCP tools
# 2. Restart server
# 3. List CTAs - data should still be there
```

## Code Changes

### Server Changes

**Before (In-Memory):**
```python
from src.storage import data_store

# Create CTA
created_cta = data_store.create_cta(cta)
```

**After (PostgreSQL):**
```python
from src.mcp_storage import mcp_storage

# Create CTA (same interface!)
created_cta = mcp_storage.create_cta(cta)
```

### No Tool Changes Required

All MCP tools work exactly the same - the storage layer is transparent:
- `create_call_to_action()` ✅ Works
- `update_health_score()` ✅ Works
- `send_survey_email()` ✅ Works
- `create_risk_alert()` ✅ Works

## Database Administration

### Viewing Data

```sql
-- List all CTAs
SELECT account_id, title, status, priority, created_at
FROM call_to_actions
ORDER BY created_at DESC;

-- Check health scores
SELECT account_id, overall_score, status, trend
FROM health_scores
ORDER BY overall_score DESC;

-- View risk alerts
SELECT account_id, risk_level, acknowledged
FROM risk_alerts
WHERE acknowledged = FALSE;

-- Survey statistics
SELECT survey_type, COUNT(*), AVG(response_score)
FROM surveys
WHERE response_received = TRUE
GROUP BY survey_type;
```

### Backup and Restore

**Backup:**
```bash
# Full database backup
pg_dump customer_success > backup.sql

# Cloud SQL backup
gcloud sql backups create --instance=customer-success-db
```

**Restore:**
```bash
# Restore from backup
psql customer_success < backup.sql

# Cloud SQL restore
gcloud sql backups restore BACKUP_ID --instance=customer-success-db
```

### Performance Monitoring

```sql
-- Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check index usage
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;

-- Active connections
SELECT count(*) FROM pg_stat_activity;
```

## Cloud Deployment

### Google Cloud SQL Setup

1. **Create Cloud SQL instance:**
```bash
gcloud sql instances create customer-success-db \
    --database-version=POSTGRES_14 \
    --tier=db-g1-small \
    --region=us-central1 \
    --authorized-networks=0.0.0.0/0  # Or specific IPs
```

2. **Create database:**
```bash
gcloud sql databases create customer_success \
    --instance=customer-success-db
```

3. **Set root password:**
```bash
gcloud sql users set-password postgres \
    --instance=customer-success-db \
    --password=your_secure_password
```

4. **Configure Cloud Run connection:**

Update `cloudbuild.yaml`:
```yaml
substitutions:
  _DB_HOST: '/cloudsql/PROJECT_ID:us-central1:customer-success-db'
  _DB_NAME: 'customer_success'
  _DB_USER: 'postgres'
  _DB_PASSWORD: 'your_secure_password'
```

5. **Run migration on Cloud SQL:**
```bash
# Connect via Cloud SQL Proxy
cloud_sql_proxy -instances=PROJECT_ID:us-central1:customer-success-db=tcp:5432

# In another terminal, run migration
DB_HOST=localhost python migrate_to_postgresql.py
```

### AWS RDS Setup

1. **Create RDS PostgreSQL instance** via AWS Console
2. **Configure security groups** to allow connections
3. **Update `.env` with RDS endpoint**
4. **Run migration script**

## Troubleshooting

### Connection Errors

**Error:** `psycopg2.OperationalError: could not connect to server`

**Solutions:**
- Check PostgreSQL is running: `brew services list` or `systemctl status postgresql`
- Verify credentials in `.env` file
- Test connection: `psql -h localhost -U postgres -d customer_success`
- Check firewall rules for cloud databases

### Migration Failures

**Error:** `relation "call_to_actions" already exists`

**Solution:** Tables already exist. Data is safe. You can ignore this or drop/recreate:
```sql
DROP TABLE IF EXISTS call_to_actions CASCADE;
DROP TABLE IF EXISTS health_scores CASCADE;
DROP TABLE IF EXISTS surveys CASCADE;
DROP TABLE IF EXISTS risk_alerts CASCADE;
```

Then run migration again.

### Performance Issues

**Slow queries?**

1. **Check indexes:**
```sql
-- Missing indexes?
SELECT * FROM pg_stat_user_tables WHERE idx_scan = 0;
```

2. **Analyze tables:**
```sql
ANALYZE call_to_actions;
ANALYZE health_scores;
ANALYZE surveys;
ANALYZE risk_alerts;
```

3. **Enable query logging:**
```sql
ALTER DATABASE customer_success SET log_statement = 'all';
```

## Data Migration from Old Servers

If you have a running server with in-memory data you want to preserve:

**Option 1: Export via MCP Tools**
1. Use `list_call_to_actions()`, `list_health_scores()`, etc. to get all data
2. Save to JSON files
3. After migration, recreate data via `create_call_to_action()`, etc.

**Option 2: Manual Recreation**
1. Document critical data before migration
2. After migration, manually recreate essential records
3. Use this as an opportunity to clean up old data

**Note:** In-memory data is typically test data, so full migration may not be needed.

## Benefits of PostgreSQL Storage

### 1. Data Persistence
```python
# Before: Data lost on restart
restart_server()  # ❌ All CTAs gone!

# After: Data persists
restart_server()  # ✅ All CTAs still there!
```

### 2. Analytics & Reporting
```sql
-- Advanced analytics not possible with in-memory storage
SELECT 
    account_id,
    COUNT(*) as cta_count,
    AVG(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completion_rate
FROM call_to_actions
GROUP BY account_id
HAVING COUNT(*) > 5;
```

### 3. Data Integrity
- ACID transactions
- Foreign key constraints
- Data validation at database level
- Automatic timestamps

### 4. Scalability
- Read replicas for high traffic
- Connection pooling
- Query optimization
- Handles millions of records

### 5. Enterprise Features
- Point-in-time recovery
- Automated backups
- High availability
- Encryption at rest

## Comparing Storage Options

| Feature | In-Memory | PostgreSQL | BigQuery | Datastore |
|---------|-----------|------------|----------|-----------|
| **Data Persistence** | ❌ No | ✅ Yes | ✅ Yes | ✅ Yes |
| **Transactions** | ❌ No | ✅ ACID | ❌ No | ❌ Limited |
| **SQL Queries** | ❌ No | ✅ Full SQL | ✅ SQL-like | ❌ No |
| **Joins** | ❌ No | ✅ Yes | ✅ Yes | ❌ No |
| **Cost** | Free | $ | $$$ | $$ |
| **Best For** | Testing | OLTP | Analytics | NoSQL |
| **Our Choice** | - | ✅ **Selected** | - | - |

**Why PostgreSQL?**
- Already configured in project
- Perfect for transactional workloads
- Supports complex queries and relationships
- Cost-effective for OLTP use cases
- Industry standard for web applications

## Support

For issues:
- Check logs: `docker-compose logs mcp-server`
- Database logs: `tail -f /var/log/postgresql/postgresql-14-main.log`
- Cloud SQL logs: `gcloud sql operations list --instance=customer-success-db`

## Summary

✅ **Migration Complete**: Your MCP server now uses PostgreSQL  
✅ **Data Persists**: Survives restarts and redeployments  
✅ **Production Ready**: Enterprise-grade reliability  
✅ **No Tool Changes**: All MCP tools work exactly the same  
✅ **Cloud Compatible**: Works with Cloud SQL, RDS, etc.  

Your Customer Success MCP Server is now production-ready! 🎉
