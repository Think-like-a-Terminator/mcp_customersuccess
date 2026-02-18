"""Test script for PostgreSQL database tools."""

from src.server import (
    test_database_connection,
    get_all_database_tables,
    get_table_schema,
    query_database,
)


def test_database_tools():
    """Test all PostgreSQL database tools."""
    print("=" * 70)
    print("PostgreSQL Database Tools - Testing")
    print("=" * 70)
    
    # Test 1: Connection Test
    print("\n1️⃣  Testing Database Connection...")
    conn_result = test_database_connection()
    
    if not conn_result["success"]:
        print(f"   ❌ Database connection failed: {conn_result.get('error', 'Unknown error')}")
        print("\n" + "=" * 70)
        print("⚠️  Database Connection Required")
        print("=" * 70)
        print("\nTo use PostgreSQL tools, you need:")
        print("1. PostgreSQL installed and running")
        print("2. Database configured in .env file:")
        print("   POSTGRES_HOST=localhost")
        print("   POSTGRES_PORT=5432")
        print("   POSTGRES_DB=customer_success")
        print("   POSTGRES_USER=postgres")
        print("   POSTGRES_PASSWORD=your-password")
        print("\n3. Create a test database:")
        print("   createdb customer_success")
        print("=" * 70)
        return
    
    print(f"   ✓ Connection successful")
    print(f"   ✓ Database: {conn_result['database']}")
    print(f"   ✓ Version: {conn_result['version'][:50]}...")
    
    # Test 2: List Tables
    print("\n2️⃣  Listing Database Tables...")
    tables_result = get_all_database_tables()
    
    if tables_result["success"]:
        tables = tables_result.get("tables", [])
        if tables:
            print(f"   ✓ Found {len(tables)} tables:")
            for table in tables[:5]:  # Show first 5
                row_count = table.get("row_count_estimate", "unknown")
                print(f"     • {table['table_name']} ({row_count} rows)")
        else:
            print("   ℹ️  No tables found in public schema")
    else:
        print(f"   ❌ Failed to list tables: {tables_result.get('error', 'Unknown error')}")
    
    # Test 3: Get Table Schema (if tables exist)
    tables = tables_result.get("tables", [])
    if tables_result["success"] and tables:
        first_table = tables[0]["table_name"]
        print(f"\n3️⃣  Getting Schema for '{first_table}' table...")
        schema_result = get_table_schema(first_table)
        
        if schema_result["success"]:
            columns = schema_result.get("columns", [])
            print(f"   ✓ Found {len(columns)} columns:")
            for col in columns[:5]:  # Show first 5 columns
                nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                print(f"     • {col['column_name']}: {col['data_type']} {nullable}")
        else:
            print(f"   ❌ Failed to get schema: {schema_result.get('error', 'Unknown error')}")
    
    # Test 4: Sample Query
    print("\n4️⃣  Testing Sample Query...")
    query = "SELECT current_database(), current_user, version()"
    query_result = query_database(username="admin", query=query)
    
    if query_result["success"]:
        print(f"   ✓ Query executed successfully")
        print(f"   ✓ Rows returned: {len(query_result['results'])}")
        if query_result["results"]:
            result = query_result["results"][0]
            print(f"   ✓ Current database: {result.get('current_database', 'N/A')}")
            print(f"   ✓ Current user: {result.get('current_user', 'N/A')}")
    else:
        print(f"   ❌ Query failed: {query_result.get('error', 'Unknown error')}")
    
    # Test 5: Safety Check (should be blocked)
    print("\n5️⃣  Testing Safety Features...")
    dangerous_query = "DROP TABLE test"
    safety_result = query_database(username="admin", query=dangerous_query)
    
    if not safety_result["success"]:
        print(f"   ✓ Dangerous operations properly blocked")
        print(f"   ✓ Protection: {safety_result['error']}")
    else:
        print(f"   ⚠️  Safety check did not work as expected")
    
    print("\n" + "=" * 70)
    print("✅ PostgreSQL Database Tools Testing Complete")
    print("=" * 70)
    print("\nAvailable Tools:")
    print("  • query_database - Execute read-only SQL queries")
    print("  • test_database_connection - Test connection")
    print("  • get_all_database_tables - List all tables")
    print("  • get_table_schema - Inspect table structure")
    print("=" * 70)


if __name__ == "__main__":
    test_database_tools()
