#!/usr/bin/env python3
"""
Database Migration Script - Add MCP Tool Tables

This script adds the necessary tables for storing MCP tool data in PostgreSQL:
- call_to_actions
- health_scores (enhanced)
- surveys
- risk_alerts

Run this after deploying to migrate from in-memory storage to PostgreSQL.

Usage:
    python migrate_to_postgresql.py
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from db_service import DatabaseService


def main():
    """Run database migration."""
    print("\n" + "=" * 70)
    print("DATABASE MIGRATION: MCP Tool Tables")
    print("=" * 70)
    print("\nThis will add tables for Call to Actions, Health Scores,")
    print("Surveys, and Risk Alerts to your PostgreSQL database.\n")
    
    # Confirm
    response = input("Continue with migration? (yes/no): ").strip().lower()
    if response != 'yes':
        print("\nMigration cancelled.")
        return 0
    
    print("\n" + "-" * 70)
    print("Connecting to database...")
    print("-" * 70)
    
    try:
        db = DatabaseService()
        
        # Test connection
        result = db.execute_query("SELECT version()", fetch_results=True)
        if result:
            print(f"✅ Connected to PostgreSQL")
            print(f"   Version: {result[0]['version'][:50]}...")
        
        print("\n" + "-" * 70)
        print("Running migrations...")
        print("-" * 70)
        
        # Read and execute init-db.sql
        sql_file = os.path.join(os.path.dirname(__file__), 'init-db.sql')
        
        if not os.path.exists(sql_file):
            print(f"❌ SQL file not found: {sql_file}")
            return 1
        
        with open(sql_file, 'r') as f:
            sql_content = f.read()
        
        # Execute SQL (split by statement if needed)
        print("\n1. Creating tables...")
        db.execute_query(sql_content, fetch_results=False)
        print("✅ Tables created/updated successfully")
        
        # Verify tables exist
        print("\n2. Verifying tables...")
        tables_query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN (
                'call_to_actions', 'health_scores', 'surveys', 'risk_alerts',
                'customers', 'users', 'api_keys'
            )
            ORDER BY table_name
        """
        
        result = db.execute_query(tables_query, fetch_results=True)
        
        if result:
            print(f"✅ Found {len(result)} tables:")
            for row in result:
                print(f"   • {row['table_name']}")
        else:
            print("⚠️  No tables found")
        
        print("\n" + "=" * 70)
        print("MIGRATION COMPLETE")
        print("=" * 70)
        print("\n✅ Your MCP server now stores data in PostgreSQL!")
        print("\nNext steps:")
        print("1. Restart your MCP server")
        print("2. Data will now persist across server restarts")
        print("3. You can query the database directly for analytics")
        print("\nTables created:")
        print("  • call_to_actions - Call to actions for accounts")
        print("  • health_scores - Account health scores with metrics")
        print("  • surveys - NPS/CSAT survey records")
        print("  • risk_alerts - Account risk alerts")
        print("  • customers - Customer/account information")
        print("\n" + "=" * 70 + "\n")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        print("\nTroubleshooting:")
        print("- Check database credentials in .env file")
        print("- Ensure PostgreSQL is running")
        print("- Verify database exists")
        print("- Check user has CREATE TABLE permissions")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
