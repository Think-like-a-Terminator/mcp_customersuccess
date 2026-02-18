# PostgreSQL Database Tools

The Customer Success MCP Server now includes tools for querying PostgreSQL databases.

## Configuration

Add these environment variables to your `.env` file:

```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=customer_success
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-password
```

## Available Tools

### 1. `query_database`
Execute SQL queries against your PostgreSQL database.

**Parameters:**
- `query` (string): SQL query to execute
- `fetch_results` (boolean, default: true): Whether to return results (true for SELECT, false for INSERT/UPDATE/DELETE)

**Safety Features:**
- Blocks dangerous operations (DROP TABLE, DROP DATABASE, TRUNCATE)
- Automatic transaction rollback on errors
- Read-only queries are safe to use

**Examples:**
```sql
-- Select queries
SELECT * FROM customers WHERE status = 'active'

-- Join queries
SELECT c.name, h.score 
FROM customers c 
JOIN health_scores h ON c.id = h.customer_id

-- Aggregate queries
SELECT status, COUNT(*) 
FROM customers 
GROUP BY status
```

### 2. `test_database_connection`
Test the database connection and retrieve server information.

**Returns:**
- Connection status
- Database name
- PostgreSQL version

**Example:**
```python
result = test_database_connection()
# Returns: {"success": true, "connected": true, "database": "customer_success", "version": "PostgreSQL 15.3..."}
```

### 3. `get_database_tables`
List all tables in the public schema with row counts.

**Returns:**
- List of tables with schema, owner, and row count

**Example:**
```python
result = get_database_tables()
# Returns: {"success": true, "results": [{"tablename": "customers", "row_count": 150}, ...]}
```

### 4. `get_table_schema`
Get detailed schema information for a specific table.

**Parameters:**
- `table_name` (string): Name of the table to inspect

**Returns:**
- Column names
- Data types
- Null constraints
- Default values
- Character limits

**Example:**
```python
result = get_table_schema("customers")
# Returns column details: name, type, nullable, default, max_length
```

## Usage Example

```python
# 1. Test connection first
connection = test_database_connection()
if connection["success"]:
    print(f"Connected to {connection['database']}")

# 2. List available tables
tables = get_database_tables()
for table in tables["results"]:
    print(f"Table: {table['tablename']} ({table['row_count']} rows)")

# 3. Get table structure
schema = get_table_schema("customers")
for column in schema["results"]:
    print(f"  - {column['column_name']}: {column['data_type']}")

# 4. Query data
result = query_database("SELECT * FROM customers LIMIT 10")
if result["success"]:
    print(f"Found {len(result['results'])} rows")
    for row in result["results"]:
        print(row)
```

## Error Handling

All tools return a consistent format:
```python
{
    "success": bool,          # Whether operation succeeded
    "results": [...],         # Query results (if applicable)
    "error": "...",          # Error message (if failed)
    "rowcount": int          # Number of affected rows
}
```

## Security Notes

1. **SQL Injection Prevention**: Always use parameterized queries when possible
2. **Blocked Operations**: DROP TABLE, DROP DATABASE, TRUNCATE are automatically blocked
3. **Transaction Safety**: All queries run in transactions with automatic rollback on error
4. **Read vs Write**: Set `fetch_results=False` for INSERT/UPDATE/DELETE operations

## Sample Database Setup

To create a sample customer success database:

```sql
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE health_scores (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    score DECIMAL(5,2) NOT NULL,
    status VARCHAR(50),
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE interactions (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    interaction_type VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert sample data
INSERT INTO customers (name, email, status) VALUES
    ('Acme Corp', 'contact@acme.com', 'active'),
    ('TechStart Inc', 'hello@techstart.com', 'active'),
    ('Global Solutions', 'info@globalsolutions.com', 'at-risk');

INSERT INTO health_scores (customer_id, score, status) VALUES
    (1, 85.5, 'excellent'),
    (2, 72.0, 'good'),
    (3, 45.0, 'at-risk');
```

## Integration with Other MCP Tools

The PostgreSQL tools can be combined with other MCP server features:

```python
# Query customers with low health scores
low_scores = query_database("""
    SELECT c.name, c.email, h.score 
    FROM customers c
    JOIN health_scores h ON c.id = h.customer_id
    WHERE h.score < 60
""")

# For each at-risk customer, create a CTA
for customer in low_scores["results"]:
    create_call_to_action(
        account_id=customer["name"],
        title=f"Check in with {customer['name']}",
        priority="high",
        due_date=datetime.now() + timedelta(days=7)
    )
```
