#!/usr/bin/env python3
"""
Setup Cloud SQL PostgreSQL Database on Google Cloud Platform

This script creates all necessary tables in Cloud SQL for the Customer Success MCP Server.
Run this after creating your Cloud SQL instance.

Usage:
    python3 setup_cloud_sql.py --instance INSTANCE_NAME --password PASSWORD
"""

import argparse
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


SQL_SCHEMA = """
-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255),
    hashed_password TEXT NOT NULL,
    disabled BOOLEAN DEFAULT FALSE,
    scopes TEXT[] DEFAULT ARRAY['read', 'write'],
    email_verified BOOLEAN DEFAULT FALSE,
    verification_token TEXT,
    verification_token_expires TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create api_keys table for API key authentication
CREATE TABLE IF NOT EXISTS api_keys (
    id SERIAL PRIMARY KEY,
    key_hash TEXT NOT NULL UNIQUE,
    key_prefix VARCHAR(20) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_by VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    last_used_at TIMESTAMP,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_is_active ON api_keys(is_active);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
"""


def main():
    parser = argparse.ArgumentParser(description='Setup Cloud SQL PostgreSQL Database')
    parser.add_argument('--host', default='127.0.0.1', help='Database host (use Cloud SQL Proxy)')
    parser.add_argument('--port', type=int, default=5432, help='Database port')
    parser.add_argument('--user', default='postgres', help='Database user')
    parser.add_argument('--password', required=True, help='Database password')
    parser.add_argument('--database', default='customer_success', help='Database name')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("CLOUD SQL POSTGRESQL SETUP")
    print("=" * 70)
    print(f"\nHost: {args.host}")
    print(f"Port: {args.port}")
    print(f"User: {args.user}")
    print(f"Database: {args.database}")
    print()
    
    try:
        # Connect to postgres database to create customer_success database
        print("Connecting to PostgreSQL...")
        conn = psycopg2.connect(
            host=args.host,
            port=args.port,
            user=args.user,
            password=args.password,
            database='postgres'
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Create database if it doesn't exist
        print(f"Creating database '{args.database}' if not exists...")
        cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{args.database}'")
        if not cursor.fetchone():
            cursor.execute(f"CREATE DATABASE {args.database}")
            print(f"✅ Database '{args.database}' created")
        else:
            print(f"✅ Database '{args.database}' already exists")
        
        cursor.close()
        conn.close()
        
        # Connect to customer_success database and create tables
        print(f"\nConnecting to '{args.database}' database...")
        conn = psycopg2.connect(
            host=args.host,
            port=args.port,
            user=args.user,
            password=args.password,
            database=args.database
        )
        cursor = conn.cursor()
        
        print("Creating tables...")
        cursor.execute(SQL_SCHEMA)
        conn.commit()
        
        # Verify tables
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        
        print("\n✅ Tables created successfully:")
        for table in tables:
            print(f"   - {table[0]}")
        
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 70)
        print("NEXT STEPS:")
        print("=" * 70)
        print("1. Generate an admin API key:")
        print("   python3 bootstrap_admin_key.py")
        print()
        print("2. Update Cloud Run environment variables:")
        print(f"   POSTGRES_HOST={args.host}")
        print(f"   POSTGRES_PASSWORD=<your-password>")
        print()
        print("3. Configure Cloud SQL Proxy connection for Cloud Run")
        print("=" * 70)
        print()
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        print("\nTroubleshooting:")
        print("1. Make sure Cloud SQL Proxy is running:")
        print("   ./cloud-sql-proxy INSTANCE_CONNECTION_NAME")
        print("2. Check your password")
        print("3. Verify firewall rules allow connections")
        return 1


if __name__ == "__main__":
    sys.exit(main())
