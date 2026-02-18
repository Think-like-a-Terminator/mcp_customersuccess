# PostgreSQL Tools - Quick Start

## ✅ What Was Added

Four new MCP tools for PostgreSQL database operations:

1. **query_database** - Execute SQL queries (SELECT, INSERT, UPDATE, DELETE)
2. **test_database_connection** - Verify database connectivity
3. **get_database_tables** - List all tables with row counts
4. **get_table_schema** - Inspect table structure and columns

## 📦 Installation

Already installed automatically with the project. The PostgreSQL driver (`psycopg2-binary`) was added to dependencies.

## ⚙️ Configuration

### 1. Add to your `.env` file:
```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=customer_success
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-password
```

### 2. Create the database (if needed):
```bash
createdb customer_success
```

### 3. Test the connection:
```bash
uv run python test_database.py
```

## 🚀 Quick Examples

### Test Connection
```python
from src.server import test_database_connection

result = test_database_connection()
# Returns: {
#   "success": true,
#   "connected": true,
#   "database": "customer_success",
#   "version": "PostgreSQL 15.3..."
# }
```

### List Tables
```python
from src.server import get_database_tables

result = get_database_tables()
# Returns: {
#   "success": true,
#   "results": [
#     {"tablename": "customers", "row_count": 150},
#     {"tablename": "health_scores", "row_count": 120}
#   ]
# }
```

### Query Data
```python
from src.server import query_database

result = query_database("SELECT * FROM customers WHERE status = 'active'")
# Returns: {
#   "success": true,
#   "results": [...],
#   "rowcount": 10
# }
```

### Get Table Structure
```python
from src.server import get_table_schema

result = get_table_schema("customers")
# Returns column details: name, type, nullable, default, max_length
```

## 🔒 Safety Features

✅ **Blocked Operations**: DROP TABLE, DROP DATABASE, TRUNCATE automatically prevented  
✅ **Transaction Safety**: Auto-rollback on errors  
✅ **Error Handling**: Detailed error messages returned  
✅ **SQL Injection Protection**: Use parameterized queries

Example of blocked operation:
```python
result = query_database("DROP TABLE customers")
# Returns: {"success": false, "error": "Dangerous operation 'DROP TABLE' is not allowed"}
```

## 📚 Documentation

- **[POSTGRESQL_TOOLS.md](POSTGRESQL_TOOLS.md)** - Complete documentation with examples
- **[README.md](README.md)** - Updated with PostgreSQL features
- **[test_database.py](test_database.py)** - Test script demonstrating all tools

## 🎯 Use Cases

### 1. Customer Health Reporting
```sql
SELECT 
    c.name,
    h.score,
    h.status,
    COUNT(i.id) as interaction_count
FROM customers c
LEFT JOIN health_scores h ON c.id = h.customer_id
LEFT JOIN interactions i ON c.id = i.customer_id
GROUP BY c.id, c.name, h.score, h.status
ORDER BY h.score ASC;
```

### 2. At-Risk Customer Analysis
```sql
SELECT 
    c.name,
    c.email,
    h.score,
    MAX(i.created_at) as last_interaction
FROM customers c
JOIN health_scores h ON c.id = h.customer_id
LEFT JOIN interactions i ON c.id = i.customer_id
WHERE h.score < 60
GROUP BY c.id, c.name, c.email, h.score
HAVING MAX(i.created_at) < NOW() - INTERVAL '30 days'
   OR MAX(i.created_at) IS NULL;
```

### 3. Integration with MCP Tools
```python
# Query at-risk customers
at_risk = query_database("""
    SELECT name, email, score 
    FROM customers c 
    JOIN health_scores h ON c.id = h.customer_id 
    WHERE h.score < 60
""")

# Create CTAs for each
for customer in at_risk["results"]:
    create_call_to_action(
        account_id=customer["name"],
        title=f"Urgent: Check in with {customer['name']}",
        priority="high"
    )
```

## 🧪 Testing

### Run database tests:
```bash
uv run python test_database.py
```

### Run all MCP server tests:
```bash
uv run python test_tools.py
```

Both test suites pass successfully! ✅

## 📝 Notes

- Tools work even if PostgreSQL is not connected (graceful error handling)
- Connection details are loaded from environment variables
- All existing MCP tools remain fully functional
- Database connection is created per-query (no persistent connections)

## 🆘 Troubleshooting

**Connection refused error:**
- Ensure PostgreSQL is running: `brew services start postgresql` (macOS)
- Check port is correct (default: 5432)
- Verify database exists: `psql -l`

**Authentication failed:**
- Check username and password in `.env`
- Verify user has access: `psql -U postgres -d customer_success`

**Table not found:**
- Use `get_database_tables()` to see available tables
- Check you're querying the correct schema (default: public)
