"""PostgreSQL database service for executing queries."""

import psycopg2
from psycopg2 import sql, Error
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
import logging
from src.config import settings

# Set up logging
logger = logging.getLogger(__name__)


class DatabaseService:
    """Service for executing PostgreSQL queries."""
    
    def __init__(self):
        """Initialize database service."""
        # Check if using Unix socket (Cloud Run) or TCP (local)
        if settings.postgres_host.startswith('/'):
            # Unix socket connection for Cloud Run
            # For psycopg2, the host should be the directory containing the socket
            self.connection_params = {
                "host": settings.postgres_host,
                "database": settings.postgres_db,
                "user": settings.postgres_user,
                "password": settings.postgres_password,
            }
            logger.info(f"DatabaseService initialized with Unix socket: {settings.postgres_host}")
        else:
            # TCP connection for local development
            self.connection_params = {
                "host": settings.postgres_host,
                "port": settings.postgres_port,
                "database": settings.postgres_db,
                "user": settings.postgres_user,
                "password": settings.postgres_password,
            }
            logger.info(f"DatabaseService initialized with TCP: {settings.postgres_host}:{settings.postgres_port}")
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = None
        try:
            conn = psycopg2.connect(**self.connection_params)
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()
    
    def execute_query(
        self, 
        query: str, 
        params: Optional[tuple] = None,
        fetch_results: bool = True
    ) -> Dict[str, Any]:
        """
        Execute a SQL query against the PostgreSQL database.
        
        Args:
            query: SQL query to execute
            params: Optional tuple of parameters for parameterized queries
            fetch_results: Whether to fetch and return results (for SELECT queries)
        
        Returns:
            Dictionary with success status, results, and metadata
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Execute the query
                    cursor.execute(query, params)
                    
                    result = {
                        "success": True,
                        "rowcount": cursor.rowcount,
                    }
                    
                    # Fetch results for SELECT queries
                    if fetch_results and cursor.description:
                        rows = cursor.fetchall()
                        result["results"] = [dict(row) for row in rows]
                        result["column_names"] = [desc[0] for desc in cursor.description]
                    else:
                        result["results"] = []
                        result["column_names"] = []
                    
                    return result
                    
        except Error as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "results": [],
                "rowcount": 0,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "error_type": type(e).__name__,
                "results": [],
                "rowcount": 0,
            }
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test the database connection.
        
        Returns:
            Dictionary with connection status and database info
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT version();")
                    version = cursor.fetchone()[0]
                    
                    cursor.execute("SELECT current_database();")
                    database = cursor.fetchone()[0]
                    
                    return {
                        "success": True,
                        "connected": True,
                        "database": database,
                        "version": version,
                    }
        except Exception as e:
            return {
                "success": False,
                "connected": False,
                "error": str(e),
            }


# Global database service instance
db_service = DatabaseService()
