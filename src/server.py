"""Customer Success MCP Server - Main server implementation."""

import asyncio
import logging
import os
import secrets
import sys
import time
import weakref
from datetime import datetime, timedelta
from typing import Any, Optional
import uuid
import io
from pathlib import Path
from contextvars import ContextVar

from mcp.server.fastmcp import FastMCP
from src.config import settings
from src.auth import authenticate_user, create_access_token
from src.models import (
    CallToAction,
    HealthScore,
    HealthScoreMetric,
    RiskAlert,
    Priority,
    CTAStatus,
    HealthScoreStatus,
    RiskLevel,
    Token,
)

from src.mcp_storage import mcp_storage
from src.api_key_service import APIKeyService
from src.oauth_service import oauth_service
from src.db_service import db_service
from src.user_service import UserService
from src.slack_service import slack_service

# Context variable to store API key info for current request
api_key_context: ContextVar[Optional[dict]] = ContextVar('api_key_context', default=None)
# Context variable to track SSE session_id for the current request
session_id_context: ContextVar[Optional[str]] = ContextVar('session_id_context', default=None)

# ── Session auth state ───────────────────────────────────────────────────────
# TTL constants
_SESSION_AUTH_TTL = 120 * 3600        # 120 hours/5 days — session auth expires
_PENDING_AUTH_REQUEST_TTL = 600     # 10 minutes — auth request link expires

# Map session_key (id of MCP session object) -> {username, scopes, created_at, session_ref}
_session_auth: dict[int, dict] = {}
# Map auth_request_id -> {session_key, session_ref, created_at}
_pending_auth_requests: dict[str, dict] = {}


def _cleanup_expired_auth():
    """Remove expired entries from _session_auth and _pending_auth_requests."""
    now = time.time()
    # Clean expired sessions (TTL or dead weakrefs)
    expired_sessions = [
        k for k, v in _session_auth.items()
        if (now - v.get('created_at', 0) > _SESSION_AUTH_TTL)
        or (v.get('session_ref') is not None and v['session_ref']() is None)
    ]
    for k in expired_sessions:
        del _session_auth[k]
    if expired_sessions:
        logger.info(f"[LAZY-AUTH] Cleaned up {len(expired_sessions)} expired session(s)")

    # Clean expired pending auth requests
    expired_pending = [
        k for k, v in _pending_auth_requests.items()
        if now - v.get('created_at', 0) > _PENDING_AUTH_REQUEST_TTL
    ]
    for k in expired_pending:
        del _pending_auth_requests[k]
    if expired_pending:
        logger.info(f"[LAZY-AUTH] Cleaned up {len(expired_pending)} expired auth request(s)")


# Initialize services
user_service = UserService()

logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP(
    name=settings.server_name,
    instructions="""
    Customer Success MCP Server provides tools for managing customer success operations,
    similar to Gainsight. Features include:
    
    - User registration and authentication
    - Call to Actions (CTAs) management
    - Account Health Score tracking
    - Account Risk Alerts and monitoring
    - PostgreSQL database queries and schema inspection
    
    Use the 'authenticate' tool to obtain an access token for protected operations.
    Database tools require PostgreSQL to be configured in environment variables.
    """,
)


# ============================================================================
# AUTHENTICATION TOOLS
# ============================================================================

@mcp.tool()
def check_auth_status() -> dict[str, Any]:
    """
    Check whether this session has been authenticated.
    
    After the user completes OAuth sign-in in the browser, their session is
    automatically activated. Call this tool to verify the session is ready.
    
    Returns:
        Authentication status for the current session
    """
    # Run cleanup on each check
    _cleanup_expired_auth()
    try:
        ctx = mcp.get_context()
        session_obj = ctx.session
        session_key = id(session_obj)
        if session_key in _session_auth:
            info = _session_auth[session_key]
            # Verify session object is still alive via weakref
            ref = info.get('session_ref')
            if ref is not None and ref() is None:
                del _session_auth[session_key]
            else:
                return {
                    "success": True,
                    "authenticated": True,
                    "message": f"Session is authenticated as {info['username']}. All tools are available.",
                    "username": info['username'],
                }
    except Exception:
        pass
    _oauth_url = os.getenv('OAUTH_PUBLIC_BASE_URL', 'http://localhost:8000').rstrip('/')
    auth_request_id = secrets.token_urlsafe(16)
    try:
        ctx = mcp.get_context()
        session_obj = ctx.session
        session_key = id(session_obj)
        _pending_auth_requests[auth_request_id] = {
            'session_key': session_key,
            'session_ref': weakref.ref(session_obj),
            'created_at': time.time(),
        }
        logger.info(f"[AUTH] check_auth_status: pending auth created for session={session_key}, req={auth_request_id[:12]}...")
    except Exception:
        pass
    sign_in_url = f"{_oauth_url}/authorize?auth_request_id={auth_request_id}"
    logger.info(f"[AUTH] check_auth_status: authentication required, sign-in URL: {sign_in_url}")
    return {
        "success": False,
        "authenticated": False,
        "error": "authentication_required",
        "message": (
            "🔐 Authentication is required for this session.\n\n"
            f"Please ask the user to open this link to sign in:\n{sign_in_url}\n\n"
            "Once they complete sign-in in the browser, their session will be "
            "automatically activated. Call this tool again after they confirm "
            "they have signed in."
        ),
        "sign_in_url": sign_in_url,
    }




# ============================================================================
# CALL TO ACTION (CTA) TOOLS
# ============================================================================

@mcp.tool()
def create_call_to_action(
    account_id: str,
    title: str,
    description: str,
    priority: str = "medium",
    owner: Optional[str] = None,
    due_date_days: Optional[int] = None,
    tags: Optional[list[str]] = None,
) -> dict[str, Any]:
    """
    Create a new Call to Action (CTA) for an account.
    
    Args:
        account_id: Account identifier
        title: CTA title
        description: Detailed description of the action needed
        priority: Priority level (low, medium, high, critical)
        owner: Assigned CSM or owner email
        due_date_days: Number of days until due (optional)
        tags: List of tags for categorization (optional)
    
    Returns:
        Created CTA details
    """
    try:
        cta = CallToAction(
            id=str(uuid.uuid4()),
            account_id=account_id,
            title=title,
            description=description,
            priority=Priority(priority),
            owner=owner,
            due_date=datetime.now() + timedelta(days=due_date_days) if due_date_days else None,
            tags=tags or [],
        )
        
        created_cta = mcp_storage.create_cta(cta)
        
        return {
            "success": True,
            "cta": created_cta.dict(),
            "message": f"CTA created successfully with ID: {created_cta.id}",
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@mcp.tool()
def list_call_to_actions(
    account_id: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
) -> dict[str, Any]:
    """
    List Call to Actions with optional filters.
    
    Args:
        account_id: Filter by account ID (optional)
        status: Filter by status - open, in_progress, completed, dismissed (optional)
        priority: Filter by priority - low, medium, high, critical (optional)
    
    Returns:
        List of CTAs matching the criteria
    """
    try:
        ctas = mcp_storage.list_ctas(
            account_id=account_id,
            status=CTAStatus(status) if status else None,
            priority=Priority(priority) if priority else None,
        )
        
        return {
            "success": True,
            "count": len(ctas),
            "ctas": [cta.dict() for cta in ctas],
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@mcp.tool()
def update_call_to_action(
    cta_id: str,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    owner: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict[str, Any]:
    """
    Update an existing Call to Action.
    
    Args:
        cta_id: CTA identifier
        status: New status - open, in_progress, completed, dismissed (optional)
        priority: New priority - low, medium, high, critical (optional)
        owner: New owner/assignee (optional)
        notes: Additional notes (optional)
    
    Returns:
        Updated CTA details
    """
    try:
        updates = {}
        if status:
            updates["status"] = CTAStatus(status)
        if priority:
            updates["priority"] = Priority(priority)
        if owner:
            updates["owner"] = owner
        if notes:
            updates["notes"] = notes
        
        updated_cta = mcp_storage.update_cta(cta_id, updates)
        
        if not updated_cta:
            return {
                "success": False,
                "error": f"CTA with ID {cta_id} not found",
            }
        
        return {
            "success": True,
            "cta": updated_cta.dict(),
            "message": "CTA updated successfully",
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@mcp.tool()
def get_call_to_action(cta_id: str) -> dict[str, Any]:
    """
    Get details of a specific Call to Action.
    
    Args:
        cta_id: CTA identifier
    
    Returns:
        CTA details
    """
    cta = mcp_storage.get_cta(cta_id)
    
    if not cta:
        return {
            "success": False,
            "error": f"CTA with ID {cta_id} not found",
        }
    
    return {
        "success": True,
        "cta": cta.dict(),
    }


# ============================================================================
# HEALTH SCORE TOOLS
# ============================================================================

@mcp.tool()
def update_health_score(
    account_id: str,
    overall_score: float,
    metrics: Optional[list[dict]] = None,
    trend: str = "stable",
    notes: Optional[str] = None,
) -> dict[str, Any]:
    """
    Update or set the health score for an account.
    
    Args:
        account_id: Account identifier
        overall_score: Overall health score (0-100)
        metrics: List of individual metrics with name, value, and weight (optional)
        trend: Trend indicator - improving, declining, or stable
        notes: Additional notes or context (optional)
    
    Returns:
        Updated health score details
    """
    try:
        # Determine status based on score
        if overall_score >= 80:
            status = HealthScoreStatus.EXCELLENT
        elif overall_score >= 60:
            status = HealthScoreStatus.GOOD
        elif overall_score >= 40:
            status = HealthScoreStatus.AT_RISK
        else:
            status = HealthScoreStatus.CRITICAL
        
        # Parse metrics if provided
        metric_objects = []
        if metrics:
            for m in metrics:
                metric_objects.append(HealthScoreMetric(
                    name=m.get("name"),
                    value=m.get("value"),
                    weight=m.get("weight", 1.0),
                ))
        
        health_score = HealthScore(
            account_id=account_id,
            overall_score=overall_score,
            status=status,
            metrics=metric_objects,
            trend=trend,
            notes=notes,
        )
        
        updated_score = mcp_storage.set_health_score(health_score)
        
        return {
            "success": True,
            "health_score": updated_score.dict(),
            "message": f"Health score updated for account {account_id}",
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@mcp.tool()
def get_health_score(account_id: str) -> dict[str, Any]:
    """
    Get the health score for a specific account.
    
    Args:
        account_id: Account identifier
    
    Returns:
        Health score details
    """
    health_score = mcp_storage.get_health_score(account_id)
    
    if not health_score:
        return {
            "success": False,
            "error": f"No health score found for account {account_id}",
        }
    
    return {
        "success": True,
        "health_score": health_score.dict(),
    }


@mcp.tool()
def list_health_scores(
    status: Optional[str] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
) -> dict[str, Any]:
    """
    List health scores with optional filters.
    
    Args:
        status: Filter by status - excellent, good, at_risk, critical (optional)
        min_score: Minimum score threshold (optional)
        max_score: Maximum score threshold (optional)
    
    Returns:
        List of health scores matching the criteria
    """
    try:
        scores = mcp_storage.list_health_scores(
            status=HealthScoreStatus(status) if status else None,
            min_score=min_score,
            max_score=max_score,
        )
        
        return {
            "success": True,
            "count": len(scores),
            "health_scores": [score.dict() for score in scores],
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


# ============================================================================
# ACCOUNT RISK ALERT TOOLS
# ============================================================================

@mcp.tool()
def create_risk_alert(
    account_id: str,
    risk_level: str,
    risk_factors: list[str],
    impact_score: float,
    recommended_actions: Optional[list[str]] = None,
    notes: Optional[str] = None,
) -> dict[str, Any]:
    """
    Create a new account risk alert.
    
    Args:
        account_id: Account identifier
        risk_level: Risk level - none, low, medium, high
        risk_factors: List of identified risk factors
        impact_score: Potential impact score (0-100)
        recommended_actions: List of recommended mitigation actions (optional)
        notes: Additional notes (optional)
    
    Returns:
        Created risk alert details
    """
    try:
        alert = RiskAlert(
            id=str(uuid.uuid4()),
            account_id=account_id,
            risk_level=RiskLevel(risk_level),
            risk_factors=risk_factors,
            impact_score=impact_score,
            recommended_actions=recommended_actions or [],
            notes=notes,
        )
        
        created_alert = mcp_storage.create_risk_alert(alert)

        # Fire-and-forget Slack notification for medium/high alerts
        if risk_level.lower() in ("medium", "high") and slack_service.is_configured:
            slack_service.notify_risk_alert(
                account_id=account_id,
                risk_level=risk_level,
                risk_factors=risk_factors,
                impact_score=impact_score,
                recommended_actions=recommended_actions or [],
                alert_id=created_alert.id,
            )

        return {
            "success": True,
            "alert": created_alert.dict(),
            "message": f"Risk alert created with ID: {created_alert.id}",
            "slack_notified": risk_level.lower() in ("medium", "high") and slack_service.is_configured,
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@mcp.tool()
def list_risk_alerts(
    account_id: Optional[str] = None,
    risk_level: Optional[str] = None,
    acknowledged: Optional[bool] = None,
) -> dict[str, Any]:
    """
    List account risk alerts with optional filters.
    
    Args:
        account_id: Filter by account ID (optional)
        risk_level: Filter by risk level - none, low, medium, high (optional)
        acknowledged: Filter by acknowledgment status (optional)
    
    Returns:
        List of risk alerts matching the criteria
    """
    try:
        alerts = mcp_storage.list_risk_alerts(
            account_id=account_id,
            risk_level=RiskLevel(risk_level) if risk_level else None,
            acknowledged=acknowledged,
        )
        
        return {
            "success": True,
            "count": len(alerts),
            "alerts": [alert.dict() for alert in alerts],
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@mcp.tool()
def acknowledge_risk_alert(
    alert_id: str,
    acknowledged_by: str,
    notes: Optional[str] = None,
) -> dict[str, Any]:
    """
    Acknowledge a risk alert to indicate it's being addressed.
    
    Args:
        alert_id: Risk alert identifier
        acknowledged_by: Person acknowledging the alert
        notes: Additional notes about the acknowledgment (optional)
    
    Returns:
        Updated risk alert details
    """
    try:
        alert = mcp_storage.acknowledge_risk_alert(alert_id, acknowledged_by, notes)
        
        if not alert:
            return {
                "success": False,
                "error": f"Risk alert with ID {alert_id} not found",
            }
        
        return {
            "success": True,
            "alert": alert.dict(),
            "message": "Risk alert acknowledged successfully",
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@mcp.tool()
def get_risk_alert(alert_id: str) -> dict[str, Any]:
    """
    Get details of a specific risk alert.
    
    Args:
        alert_id: Risk alert identifier
    
    Returns:
        Risk alert details
    """
    alert = mcp_storage.get_risk_alert(alert_id)
    
    if not alert:
        return {
            "success": False,
            "error": f"Risk alert with ID {alert_id} not found",
        }
    
    return {
        "success": True,
        "alert": alert.dict(),
    }


# ============================================================================
# DATABASE QUERY TOOLS
# ============================================================================

@mcp.tool()
def query_database(
    query: str,
    fetch_results: bool = True,
    max_rows: int = 10000,
) -> dict[str, Any]:
    """
    Execute a READ-ONLY SQL query against the PostgreSQL database.
    
    This tool allows ONLY SELECT queries for reading data. All write operations
    (INSERT, UPDATE, DELETE, MERGE) are blocked for security.
    
    **IMPORTANT: Results are automatically limited to prevent memory/timeout issues.**
    - Default limit: 10000 rows
    - Maximum limit: 10000 rows (LLM context window constraint)
    - For larger datasets, use aggregations (COUNT, SUM, AVG).
    
    Safety features:
    - STRICTLY read-only: Only SELECT statements allowed
    - No INSERT, UPDATE, DELETE, MERGE, or CREATE operations
    - No DROP, TRUNCATE, or ALTER operations
    - Automatic row limiting to prevent timeouts
    - Uses standard PostgreSQL SQL syntax
    
    Examples:
    - SELECT queries: "SELECT * FROM customers WHERE status = 'active'"
    - JOIN queries: "SELECT c.name, h.score FROM customers c JOIN health_scores h ON c.id = h.customer_id"
    - Aggregate queries: "SELECT status, COUNT(*) FROM customers GROUP BY status"
    - Large datasets: "SELECT COUNT(*) as total FROM large_table" (use aggregations!)
    
    Args:
        query: SQL query to execute (SELECT statements only)
        fetch_results: Whether to return query results (should be True for SELECT)
        max_rows: Maximum rows to return (default: 10000, max: 10000)
    
    Returns:
        Query results with success status, row count, and data
    """
    
    # Enforce maximum row limit to prevent memory/context issues
    MAX_ALLOWED_ROWS = 10000
    if max_rows > MAX_ALLOWED_ROWS:
        max_rows = MAX_ALLOWED_ROWS
    if max_rows < 1:
        max_rows = 10000
    
    # STRICT validation - only allow SELECT queries (read-only)
    query_upper = query.strip().upper()
    
    # Block ALL write operations
    write_keywords = [
        'INSERT', 'UPDATE', 'DELETE', 'MERGE', 'CREATE', 'DROP', 
        'ALTER', 'TRUNCATE', 'REPLACE', 'GRANT', 'REVOKE'
    ]
    
    for keyword in write_keywords:
        # Check if the keyword appears as a statement (not in strings or table names)
        if keyword in query_upper:
            # More precise check: keyword followed by whitespace or specific SQL keywords
            import re
            pattern = rf'\b{keyword}\b'
            if re.search(pattern, query_upper):
                return {
                    "success": False,
                    "error": f"Write operation '{keyword}' is not allowed. This tool is READ-ONLY.",
                    "results": [],
                }
    
    # Ensure query starts with SELECT, WITH, or is a comment
    query_start = query_upper.lstrip()
    if not (query_start.startswith('SELECT') or query_start.startswith('WITH') or query_start.startswith('--')):
        return {
            "success": False,
            "error": "Only SELECT queries are allowed. This tool is READ-ONLY.",
            "results": [],
        }
    
    try:
        # Check if query already has a LIMIT clause
        has_limit = 'LIMIT' in query_upper
        
        # Add LIMIT clause if not present to prevent massive result sets
        if not has_limit:
            # Remove trailing semicolon if present, add LIMIT, then add semicolon back
            modified_query = query.rstrip().rstrip(';')
            modified_query = f"{modified_query} LIMIT {max_rows + 1}"  # +1 to detect truncation
        else:
            modified_query = query
        
        result = db_service.execute_query(modified_query, fetch_results=fetch_results)
        
        # Check if results were truncated
        if result.get("success") and fetch_results:
            results = result.get("results", [])
            was_truncated = False
            
            if not has_limit and len(results) > max_rows:
                # We got more rows than max_rows, so results were truncated
                results = results[:max_rows]
                was_truncated = True
            
            return {
                "success": True,
                "row_count": len(results),
                "max_rows_limit": max_rows,
                "was_truncated": was_truncated,
                "truncation_warning": f"Results limited to {max_rows} rows. Use aggregations (COUNT, SUM, etc.) for large datasets." if was_truncated else None,
                "results": results,
            }
        
        return result
    except Exception as e:
        return {
            "success": False,
            "error": f"Query execution failed: {str(e)}",
            "results": [],
        }


@mcp.tool()
def test_database_connection() -> dict[str, Any]:
    """
    Test the PostgreSQL database connection and retrieve database information.
    
    Use this tool to verify that the database is accessible and properly configured.
    Returns connection status, database name, and PostgreSQL version.
    
    Returns:
        Connection status and database information
    """
    try:
        result = db_service.test_connection()
        if not result.get("success"):
            return result
        
        # Also return user count for extra context
        user_result = db_service.execute_query("SELECT COUNT(*) as count FROM users;")
        user_count = user_result["results"][0]["count"] if user_result.get("success") and user_result.get("results") else 0
        
        return {
            **result,
            "postgres_host": settings.postgres_host,
            "user_count": user_count,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@mcp.tool()
def get_all_database_tables() -> dict[str, Any]:
    """
    List all tables in the current PostgreSQL database schema.
    
    Retrieves information about all tables in the public schema including
    table names and row counts (estimates).
    
    Returns:
        List of tables with metadata
    """
    try:
        tables_query = """
            SELECT
                t.table_name,
                t.table_type,
                COALESCE(s.n_live_tup, 0) AS row_count_estimate
            FROM information_schema.tables t
            LEFT JOIN pg_stat_user_tables s ON s.relname = t.table_name
            WHERE t.table_schema = 'public'
            ORDER BY t.table_name;
        """
        tables_result = db_service.execute_query(tables_query, fetch_results=True)
        
        if not tables_result.get("success"):
            return {
                "success": False,
                "error": tables_result.get("error", "Failed to retrieve tables"),
                "tables": [],
            }
        
        tables = tables_result.get("results", [])
        tables_with_columns = []
        
        for table in tables:
            table_name = table.get("table_name")
            columns_query = """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                ORDER BY ordinal_position;
            """
            columns_result = db_service.execute_query(columns_query, params=(table_name,), fetch_results=True)
            columns = columns_result.get("results", [])
            
            tables_with_columns.append({
                "table_name": table_name,
                "table_type": table.get("table_type"),
                "row_count_estimate": table.get("row_count_estimate", 0),
                "columns": columns,
            })
        
        return {
            "success": True,
            "database": settings.postgres_db,
            "table_count": len(tables_with_columns),
            "tables": tables_with_columns,
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to retrieve tables: {str(e)}",
            "tables": [],
        }


@mcp.tool()
def get_table_schema(table_name: str) -> dict[str, Any]:
    """
    Get the schema/structure of a specific table including columns and data types.
    
    Retrieves detailed information about table columns including:
    - Column names
    - Data types
    - Null constraints
    - Default values
    - Character limits
    
    Args:
        table_name: Name of the table to describe
    
    Returns:
        Table schema information
    """
    query = """
        SELECT
            column_name,
            data_type,
            is_nullable,
            column_default,
            character_maximum_length,
            ordinal_position
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position;
    """
    
    try:
        result = db_service.execute_query(query, params=(table_name,), fetch_results=True)
        
        if result["success"] and not result.get("results"):
            return {
                "success": False,
                "error": f"Table '{table_name}' not found or has no columns",
                "results": [],
            }
        
        return {
            "success": result["success"],
            "table_name": table_name,
            "column_count": len(result.get("results", [])),
            "columns": result.get("results", []),
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to retrieve schema: {str(e)}",
            "results": [],
        }


# ============================================================================
# CRM SYNC TOOLS
# ============================================================================

@mcp.tool()
def sync_from_crm(
    crm: str,
    limit: int = 200,
) -> dict[str, Any]:
    """
    Sync account data from a connected CRM (Salesforce or HubSpot) into the
    local customers table.

    Accounts are upserted by external ID so running this repeatedly is safe.
    Configure credentials via environment variables before calling:

    **Salesforce:** Set SALESFORCE_USERNAME, SALESFORCE_PASSWORD,
    SALESFORCE_SECURITY_TOKEN (and optionally SALESFORCE_DOMAIN=test for sandboxes).

    **HubSpot:** Set HUBSPOT_API_KEY.

    Args:
        crm: CRM to sync from — "salesforce" or "hubspot"
        limit: Maximum number of accounts to pull (default 200, max 200)

    Returns:
        Sync result with number of accounts upserted

    Example:
        sync_from_crm(crm="salesforce")
        sync_from_crm(crm="hubspot", limit=50)
    """
    try:
        from src.crm_service import get_crm_syncer
        syncer = get_crm_syncer(crm)
        return syncer.sync(limit=min(limit, 200))
    except ValueError as exc:
        return {"success": False, "error": str(exc)}
    except Exception as exc:
        return {
            "success": False,
            "error": f"CRM sync failed: {exc}",
            "error_type": type(exc).__name__,
        }


def main():
    """For testing purposes. Run the MCP server in stdio mode."""
    mcp.run(transport="stdio")


def create_sse_app():
    """
    Create the SSE app for HTTP/Cloud Run deployment.

    Authentication supports two schemes (checked in order):
      1. OAuth 2.1 Bearer token  — Authorization: Bearer <token>
      2. Legacy API key          — X-API-Key: <key>

    OAuth 2.1 endpoints (unauthenticated, per MCP spec):
      GET  /.well-known/oauth-authorization-server  — RFC8414 metadata
      GET  /.well-known/oauth-protected-resource    — RFC9728 metadata
      GET  /authorize                               — show login form
      POST /authorize                               — submit credentials, issue code
      POST /token                                   — exchange code / refresh token
      POST /register                                — dynamic client registration (RFC7591)
      POST /revoke                                  — token revocation
    """
    import os
    import urllib.parse
    from starlette.requests import Request
    from starlette.responses import HTMLResponse, JSONResponse, Response
    from starlette.routing import Route
    from mcp.server.transport_security import TransportSecuritySettings

    # Disable DNS-rebinding protection in cloud environments
    if os.environ.get("K_SERVICE") or os.environ.get("PORT"):
        mcp.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        )

    api_key_service = APIKeyService()

    # ── Helpers ──────────────────────────────────────────────────────────────

    # def _base_url(request: Request) -> str:
    #     """Derive the OAuth base URL from the incoming request."""
    #     # Respect X-Forwarded-Proto set by Cloud Run / reverse proxies
    #     proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    #     host = request.headers.get("x-forwarded-host", request.headers.get("host", "localhost:8000"))
    #     return f"{proto}://{host}"

    def _base_url(request: Request) -> str:
        """Derive the OAuth base URL from the incoming request."""
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        host = request.headers.get("x-forwarded-host", request.headers.get("host", "localhost:8000"))
        return f"{proto}://{host}"

    def _public_base_url(request: Request) -> str:
        """Base URL reachable by the end-user's browser (for authorization_endpoint).
        Falls back to the request-derived URL if not set."""
        override = os.getenv("OAUTH_PUBLIC_BASE_URL")
        if override:
            return override.rstrip("/")
        return _base_url(request)

    def _error(message: str, status: int = 400) -> JSONResponse:
        return JSONResponse({"error": message}, status_code=status)

    # ── OAuth 2.1 Endpoints ──────────────────────────────────────────────────

    # async def oauth_server_metadata(request: Request) -> JSONResponse:
    #     """RFC8414 — Authorization Server Metadata."""
    #     return JSONResponse(oauth_service.get_server_metadata(_base_url(request)))

    async def oauth_server_metadata(request: Request) -> JSONResponse:
        """RFC8414 — Authorization Server Metadata."""
        metadata = oauth_service.get_server_metadata(_base_url(request))
        # Only override authorization_endpoint for browser access
        public = _public_base_url(request)
        metadata["authorization_endpoint"] = f"{public}/authorize"
        return JSONResponse(metadata)

    async def oauth_protected_resource(request: Request) -> JSONResponse:
        """RFC9728 — Protected Resource Metadata."""
        # Use _base_url (request-derived) NOT _public_base_url
        # because LibreChat calls this server-to-server from inside Docker
        return JSONResponse(oauth_service.get_protected_resource_metadata(_base_url(request)))

    async def oauth_register(request: Request) -> JSONResponse:
        """RFC7591 — Dynamic Client Registration."""
        try:
            body = await request.json()
        except Exception:
            return _error("Invalid JSON body")

        redirect_uris = body.get("redirect_uris", [])
        if not redirect_uris:
            return _error("redirect_uris is required")

        client_name = body.get("client_name", "MCP Client")
        try:
            result = oauth_service.register_client(
                client_name=client_name,
                redirect_uris=redirect_uris,
                grant_types=body.get("grant_types"),
                response_types=body.get("response_types"),
                scope=body.get("scope"),
                token_endpoint_auth_method=body.get("token_endpoint_auth_method", "none"),
            )
            return JSONResponse(result, status_code=201)
        except ValueError as e:
            return _error(str(e))
        except Exception as e:
            logger.error(f"Client registration failed: {e}")
            return _error("Registration failed", 500)

    # HTML login page served for GET /authorize
    _LOGIN_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sign In — Customer Success MCP</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{
      margin: 0; display: flex; align-items: center; justify-content: center;
      min-height: 100vh; background: #f0f2f5;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    .card {{
      background: #fff; border-radius: 12px; padding: 2.5rem 2rem;
      box-shadow: 0 4px 24px rgba(0,0,0,.10); width: 100%; max-width: 400px;
    }}
    h1 {{ margin: 0 0 .25rem; font-size: 1.4rem; color: #111; }}
    p.sub {{ margin: 0 0 1.75rem; font-size: .9rem; color: #666; }}
    label {{ display: block; font-size: .85rem; font-weight: 600;
             color: #333; margin-bottom: .35rem; }}
    input[type=text], input[type=password] {{
      width: 100%; padding: .65rem .85rem; border: 1px solid #ddd;
      border-radius: 8px; font-size: 1rem; outline: none;
      transition: border-color .15s;
    }}
    input:focus {{ border-color: #4f46e5; }}
    .field {{ margin-bottom: 1.1rem; }}
    .error {{
      background: #fef2f2; color: #b91c1c; border: 1px solid #fca5a5;
      border-radius: 8px; padding: .65rem .85rem; font-size: .875rem;
      margin-bottom: 1rem;
    }}
    button {{
      width: 100%; padding: .75rem; background: #4f46e5; color: #fff;
      border: none; border-radius: 8px; font-size: 1rem; font-weight: 600;
      cursor: pointer; transition: background .15s;
    }}
    button:hover {{ background: #4338ca; }}
    .scope-box {{
      background: #f8f9ff; border: 1px solid #e0e7ff; border-radius: 8px;
      padding: .65rem .85rem; font-size: .825rem; color: #4f46e5;
      margin-bottom: 1.25rem;
    }}
  </style>
</head>
<body>
  <div class="card">
    <h1>&#128274; Sign In</h1>
    <p class="sub">Customer Success MCP Server</p>
    {error_block}
    {scope_block}
    <form method="POST" action="/authorize">
      <input type="hidden" name="client_id"             value="{client_id}">
      <input type="hidden" name="redirect_uri"          value="{redirect_uri}">
      <input type="hidden" name="state"                 value="{state}">
      <input type="hidden" name="scope"                 value="{scope}">
      <input type="hidden" name="code_challenge"        value="{code_challenge}">
      <input type="hidden" name="code_challenge_method" value="{code_challenge_method}">
      <div class="field">
        <label for="username">Username</label>
        <input id="username" type="text" name="username"
               autocomplete="username" required autofocus>
      </div>
      <div class="field">
        <label for="password">Password</label>
        <input id="password" type="password" name="password"
               autocomplete="current-password" required>
      </div>
      <button type="submit">Sign In</button>
    </form>
  </div>
</body>
</html>
"""

    async def oauth_authorize(request: Request):
        """GET — show login form; POST — validate credentials, issue code, redirect."""
        from src.auth import authenticate_user

        if request.method == "GET":
            params = dict(request.query_params)
            logger.info(f"[OAUTH] GET /authorize params: {params}")
            response_type = params.get("response_type", "code")  # OAuth 2.1 only supports "code"
            client_id     = params.get("client_id", "")
            redirect_uri  = params.get("redirect_uri", "")
            state         = params.get("state", "")
            scope         = params.get("scope", "read write")
            code_challenge        = params.get("code_challenge", "")
            code_challenge_method = params.get("code_challenge_method", "S256")

            # Validate required params
            if response_type != "code":
                return _error("response_type must be 'code'")
            if not client_id or not redirect_uri:
                # ── Missing params: show a self-bootstrapping page ───────
                # LibreChat or a browser may land here without query params.
                # Render a page that does dynamic client registration + PKCE
                # setup via JavaScript then redirects back with proper params.
                # The PKCE verifier is encoded into the state param (base64 JSON)
                # so it survives across tabs/windows without needing sessionStorage.
                _pub = os.getenv("OAUTH_PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
                bootstrap_html = f"""<!DOCTYPE html>
<html><head><title>Sign In — Customer Success MCP</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         display:flex; justify-content:center; align-items:center; min-height:100vh;
         margin:0; background:#f0f2f5; color:#333; }}
  .card {{ background:#fff; padding:2.5rem; border-radius:12px; box-shadow:0 4px 24px rgba(0,0,0,.1);
           max-width:480px; width:90%; text-align:center; }}
  h2 {{ margin-top:0; color:#1a73e8; }}
  .status {{ margin:1.5rem 0; padding:1rem; border-radius:8px; background:#f8f9fa; font-size:.95rem; }}
  .error {{ background:#fce8e6; color:#d93025; }}
  .spinner {{ display:inline-block; width:20px; height:20px; border:3px solid #ddd;
              border-top-color:#1a73e8; border-radius:50%; animation:spin .8s linear infinite; }}
  @keyframes spin {{ to {{ transform:rotate(360deg); }} }}
</style></head>
<body><div class="card">
  <h2>&#128274; Customer Success MCP</h2>
  <div class="status" id="status"><span class="spinner"></span> Setting up secure connection&hellip;</div>
</div>
<script>
function randomUUID() {{
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {{
    try {{ return crypto.randomUUID(); }} catch(e) {{}}
  }}
  var buf = new Uint8Array(16);
  crypto.getRandomValues(buf);
  buf[6] = buf[6] & 0x0f | 0x40; buf[8] = buf[8] & 0x3f | 0x80;
  var h = Array.from(buf, function(x){{ return ('0'+x.toString(16)).slice(-2); }}).join('');
  return h.slice(0,8)+'-'+h.slice(8,12)+'-'+h.slice(12,16)+'-'+h.slice(16,20)+'-'+h.slice(20);
}}

(async function() {{
  const S = document.getElementById('status');
  const BASE = '{_pub}';
  try {{
    // 1. Dynamic Client Registration
    S.innerHTML = '<span class="spinner"></span> Registering client&hellip;';
    const regResp = await fetch(BASE + '/register', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{
        client_name: 'MCP Browser Login',
        redirect_uris: [BASE + '/authorize/callback', window.location.origin + '/oauth/callback', 'http://localhost:3080/oauth/callback'],
        grant_types: ['authorization_code', 'refresh_token'],
        response_types: ['code'],
        token_endpoint_auth_method: 'none'
      }})
    }});
    if (!regResp.ok) throw new Error('Registration failed: ' + await regResp.text());
    const reg = await regResp.json();
    const clientId = reg.client_id;

    // 2. Generate PKCE challenge (server-side — works on any HTTP server)
    S.innerHTML = '<span class="spinner"></span> Generating secure challenge&hellip;';
    const pkceResp = await fetch(BASE + '/pkce-generate');
    if (!pkceResp.ok) throw new Error('PKCE generation failed');
    const pkce = await pkceResp.json();
    const codeVerifier = pkce.code_verifier;
    const codeChallenge = pkce.code_challenge;

    // 3. Encode verifier + client info + auth_request_id into state
    const redirectUri = BASE + '/authorize/callback';
    const urlParams = new URLSearchParams(window.location.search);
    const authRequestId = urlParams.get('auth_request_id') || '';
    const statePayload = JSON.stringify({{
      nonce: randomUUID(),
      code_verifier: codeVerifier,
      client_id: clientId,
      redirect_uri: redirectUri,
      auth_request_id: authRequestId
    }});
    const stateB64 = btoa(statePayload).replace(/\\+/g,'-').replace(/\\//g,'_').replace(/=+$/,'');

    // 4. Redirect to /authorize with proper params
    S.innerHTML = '<span class="spinner"></span> Redirecting to login&hellip;';
    const params = new URLSearchParams({{
      response_type: 'code',
      client_id: clientId,
      redirect_uri: redirectUri,
      code_challenge: codeChallenge,
      code_challenge_method: 'S256',
      scope: 'read write',
      state: stateB64
    }});
    window.location.href = BASE + '/authorize?' + params.toString();
  }} catch(e) {{
    S.className = 'status error';
    S.textContent = '\\u274c ' + e.message;
  }}
}})();
</script></body></html>"""
                return HTMLResponse(bootstrap_html)

            client = oauth_service.get_client(client_id)
            if not client:
                return _error("Unknown client_id", 400)
            if redirect_uri not in client["redirect_uris"]:
                return _error("redirect_uri not registered for this client", 400)

            scope_block = f'<div class="scope-box">&#128274; Requesting access: <strong>{scope}</strong></div>' if scope else ""
            html = _LOGIN_HTML.format(
                client_id=client_id,
                redirect_uri=redirect_uri,
                state=state,
                scope=scope,
                code_challenge=code_challenge,
                code_challenge_method=code_challenge_method,
                error_block="",
                scope_block=scope_block,
            )
            return HTMLResponse(html)

        # POST — process login form
        form = await request.form()
        client_id             = form.get("client_id", "")
        redirect_uri          = form.get("redirect_uri", "")
        state                 = form.get("state", "")
        scope                 = form.get("scope", "read write")
        code_challenge        = form.get("code_challenge", "")
        code_challenge_method = form.get("code_challenge_method", "S256")
        username              = form.get("username", "")
        password              = form.get("password", "")

        def _show_error(msg: str):
            scope_block = f'<div class="scope-box">&#128274; Requesting access: <strong>{scope}</strong></div>' if scope else ""
            html = _LOGIN_HTML.format(
                client_id=client_id,
                redirect_uri=redirect_uri,
                state=state,
                scope=scope,
                code_challenge=code_challenge,
                code_challenge_method=code_challenge_method,
                error_block=f'<div class="error">{msg}</div>',
                scope_block=scope_block,
            )
            return HTMLResponse(html, status_code=401)

        # Authenticate user
        user = authenticate_user(username, password)
        if not user:
            return _show_error("Invalid username or password.")

        # Fetch user ID from DB
        try:
            from src.user_service import UserService as _US
            _us = _US()
            user_dict = _us.get_user_by_username(username)
            user_id = user_dict["id"]
        except Exception as e:
            logger.error(f"Could not fetch user ID for {username}: {e}")
            return _show_error("Internal error. Please try again.")

        # Create authorization code
        try:
            code = oauth_service.create_auth_code(
                client_id=client_id,
                user_id=user_id,
                redirect_uri=redirect_uri,
                scope=scope,
                code_challenge=code_challenge,
                code_challenge_method=code_challenge_method,
            )
        except Exception as e:
            logger.error(f"Failed to create auth code: {e}")
            return _show_error("Authorization failed. Please try again.")

        # Redirect back to client
        qs = urllib.parse.urlencode({"code": code, "state": state})
        return Response(
            status_code=302,
            headers={"location": f"{redirect_uri}?{qs}"},
        )

    async def oauth_authorize_callback(request: Request):
        """GET /authorize/callback — handle redirect after login, exchange code for token via JS."""
        params = dict(request.query_params)
        code = params.get("code", "")
        state = params.get("state", "")
        error = params.get("error", "")
        _pub = os.getenv("OAUTH_PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")

        callback_html = f"""<!DOCTYPE html>
<html><head><title>Authenticating…</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         display:flex; justify-content:center; align-items:center; min-height:100vh;
         margin:0; background:#f0f2f5; color:#333; }}
  .card {{ background:#fff; padding:2.5rem; border-radius:12px; box-shadow:0 4px 24px rgba(0,0,0,.1);
           max-width:500px; width:90%; text-align:center; }}
  h2 {{ margin-top:0; color:#1a73e8; }}
  .status {{ margin:1.5rem 0; padding:1rem; border-radius:8px; background:#f8f9fa; font-size:.95rem; word-break:break-all; }}
  .error {{ background:#fce8e6; color:#d93025; }}
  .success {{ background:#e6f4ea; color:#1e8e3e; }}
  .token-box {{ text-align:left; background:#f8f9fa; padding:1rem; border-radius:8px; margin:1rem 0;
                font-family:monospace; font-size:.85rem; word-break:break-all; max-height:200px; overflow-y:auto; }}
  .spinner {{ display:inline-block; width:20px; height:20px; border:3px solid #ddd;
              border-top-color:#1a73e8; border-radius:50%; animation:spin .8s linear infinite; }}
  @keyframes spin {{ to {{ transform:rotate(360deg); }} }}
  button {{ background:#1a73e8; color:#fff; border:none; padding:.75rem 1.5rem; border-radius:8px;
           font-size:1rem; cursor:pointer; margin-top:1rem; }} button:hover {{ background:#1557b0; }}
</style></head>
<body><div class="card">
  <h2>&#128274; Customer Success MCP</h2>
  <div class="status" id="status"><span class="spinner"></span> Exchanging authorization code&hellip;</div>
  <div id="result"></div>
</div>
<script>
(async function() {{
  const S = document.getElementById('status');
  const R = document.getElementById('result');
  const code = '{code}';
  const error = '{error}';
  const stateB64 = '{state}';
  const BASE = '{_pub}';

  if (error) {{
    S.className = 'status error';
    S.textContent = '\\u274c Authorization denied: ' + error;
    return;
  }}
  if (!code) {{
    S.className = 'status error';
    S.textContent = '\\u274c No authorization code received.';
    return;
  }}

  // Decode PKCE verifier and client info from state parameter
  let codeVerifier, clientId, redirectUri;
  try {{
    // Restore base64url padding and decode
    let b64 = stateB64.replace(/-/g,'+').replace(/_/g,'/');
    while (b64.length % 4) b64 += '=';
    const stateObj = JSON.parse(atob(b64));
    codeVerifier = stateObj.code_verifier;
    clientId = stateObj.client_id;
    redirectUri = stateObj.redirect_uri;
  }} catch(e) {{
    S.className = 'status error';
    S.textContent = '\\u274c Could not decode authentication state. Please start over.';
    R.innerHTML = '<a href="' + BASE + '/authorize"><button>Try Again</button></a>';
    return;
  }}

  if (!codeVerifier) {{
    S.className = 'status error';
    S.textContent = '\\u274c PKCE verifier not found in state. Please start over.';
    R.innerHTML = '<a href="' + BASE + '/authorize"><button>Try Again</button></a>';
    return;
  }}

  try {{
    const resp = await fetch(BASE + '/token', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
      body: new URLSearchParams({{
        grant_type: 'authorization_code',
        code: code,
        redirect_uri: redirectUri || (BASE + '/authorize/callback'),
        client_id: clientId || '',
        code_verifier: codeVerifier
      }})
    }});
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error_description || data.error || 'Token exchange failed');

    // Auto-activate the MCP session via the auth_request_id
    S.innerHTML = '<span class="spinner"></span> Activating session&hellip;';
    let authRequestId = '';
    try {{
      let b64s = stateB64.replace(/-/g,'+').replace(/_/g,'/');
      while (b64s.length % 4) b64s += '=';
      const so = JSON.parse(atob(b64s));
      authRequestId = so.auth_request_id || '';
    }} catch(ignore) {{}}

    const actResp = await fetch(BASE + '/complete-auth', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json', 'Authorization': 'Bearer ' + data.access_token}},
      body: JSON.stringify({{ auth_request_id: authRequestId }})
    }});
    const actData = await actResp.json();

    S.className = 'status success';
    S.textContent = '\\u2705 Authentication successful!';
    R.innerHTML = '<p style="font-size:1.1rem;margin-bottom:.5rem">Your session has been activated.</p>' +
      '<p style="font-size:.95rem;color:#555">You can close this tab and return to the chat.<br>' +
      'Just ask the AI to try again \\u2014 your tools are now unlocked.</p>' +
      '<p style="font-size:.85rem;color:#999;margin-top:1rem">Signed in as: ' + (actData.username || 'user') + '</p>';
  }} catch(e) {{
    S.className = 'status error';
    S.textContent = '\\u274c ' + e.message;
    R.innerHTML = '<a href="' + BASE + '/authorize"><button>Try Again</button></a>';
  }}
}})();
</script></body></html>"""
        return HTMLResponse(callback_html)

    async def oauth_pkce_generate(request: Request) -> JSONResponse:
        """GET /pkce-generate — generate a PKCE code_verifier + code_challenge pair.

        Moves SHA-256 hashing to the server so the browser JS doesn't need
        crypto.subtle (which requires a Secure Context / HTTPS).
        """
        import hashlib, base64
        code_verifier = secrets.token_urlsafe(32)  # ~43 chars, URL-safe
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        return JSONResponse({
            "code_verifier": code_verifier,
            "code_challenge": code_challenge,
        })

    async def oauth_complete_auth(request: Request) -> JSONResponse:
        """POST /complete-auth — auto-activate an MCP session after OAuth login."""
        # Require a valid Bearer token (just issued by /token)
        auth_header = request.headers.get("authorization", "")
        if not auth_header.lower().startswith("bearer "):
            return JSONResponse({"error": "Bearer token required"}, status_code=401)
        token_info = oauth_service.validate_access_token(auth_header[7:].strip())
        if not token_info:
            return JSONResponse({"error": "Invalid or expired token"}, status_code=401)

        username = token_info.get('username', token_info.get('sub', 'unknown'))

        try:
            body = await request.json()
        except Exception:
            body = {}
        auth_request_id = body.get("auth_request_id", "")

        if auth_request_id and auth_request_id in _pending_auth_requests:
            pending = _pending_auth_requests[auth_request_id]
            # Check TTL before accepting
            if time.time() - pending.get('created_at', 0) > _PENDING_AUTH_REQUEST_TTL:
                del _pending_auth_requests[auth_request_id]
                return JSONResponse({"error": "Auth request expired. Please start over."}, status_code=400)
            del _pending_auth_requests[auth_request_id]
            session_key = pending['session_key']
            # Store auth with weakref + timestamp
            session_ref = pending.get('session_ref')  # weakref to session object
            _session_auth[session_key] = {
                'username': username,
                'scopes': token_info.get('scopes', ['read', 'write']),
                'session_auth': True,
                'created_at': time.time(),
                'session_ref': session_ref,
            }
            logger.info(f"[LAZY-AUTH] Session {session_key} auto-activated as {username} via auth_request_id {auth_request_id[:12]}...")
            return JSONResponse({"success": True, "username": username, "message": "Session activated"})
        else:
            logger.warning(f"[LAZY-AUTH] /complete-auth called with invalid/missing auth_request_id: {auth_request_id[:20] if auth_request_id else '(empty)'}")
            return JSONResponse(
                {"error": "Invalid or expired auth_request_id. Please start the sign-in flow again from the chat."},
                status_code=400,
            )

    async def oauth_token(request: Request) -> JSONResponse:
        """POST /token — Authorization Code exchange and Refresh Token grant."""
        try:
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                body = await request.json()
            else:
                form = await request.form()
                body = dict(form)
            logger.info(f"Token request: grant_type={body.get('grant_type')}")
        except Exception:
            return _error("Invalid request body")

        grant_type = body.get("grant_type", "")

        if grant_type == "authorization_code":
            code          = body.get("code", "")
            redirect_uri  = body.get("redirect_uri", "")
            client_id     = body.get("client_id", "")  # optional — resolved from auth code if missing
            code_verifier = body.get("code_verifier", "")

            if not all([code, redirect_uri, code_verifier]):
                return _error("code, redirect_uri and code_verifier are required")

            try:
                tokens = oauth_service.exchange_code(
                    code=code,
                    redirect_uri=redirect_uri,
                    code_verifier=code_verifier,
                    client_id=client_id or None,
                )
                return JSONResponse(tokens)
            except ValueError as e:
                return _error(str(e), 400)
            except Exception as e:
                logger.error(f"Token exchange error: {e}")
                return _error("Token exchange failed", 500)

        if grant_type == "refresh_token":
            refresh_token = body.get("refresh_token", "")
            client_id     = body.get("client_id", "")  # optional — resolved from token record if missing

            if not refresh_token:
                return _error("refresh_token is required")

            try:
                tokens = oauth_service.refresh_access_token(
                    refresh_token=refresh_token,
                    client_id=client_id or None,
                )
                return JSONResponse(tokens)
            except ValueError as e:
                return _error(str(e), 400)
            except Exception as e:
                logger.error(f"Token refresh error: {e}")
                return _error("Token refresh failed", 500)

        return _error(f"Unsupported grant_type: {grant_type}")

    async def oauth_revoke(request: Request) -> JSONResponse:
        """POST /revoke — Token revocation (RFC7009)."""
        try:
            form = await request.form()
            token = form.get("token", "")
        except Exception:
            return _error("Invalid request")

        if not token:
            return _error("token is required")

        oauth_service.revoke_token(token)
        return JSONResponse({"revoked": True})

    # ── Auth Middleware (LAZY AUTH) ─────────────────────────────────────────
    # SSE connections, tool discovery, AND tool execution all pass through
    # at the HTTP level. Auth is enforced inside each tool function instead,
    # so the MCP protocol stays happy and the model gets a useful error
    # message (not a transport-level 401 that triggers circuit breakers).

    _PUBLIC_PATHS = {
        "/", "/health", "/authorize", "/authorize/callback", "/token", "/register", "/revoke",
        "/complete-auth", "/pkce-generate",
        "/.well-known/oauth-authorization-server",
        "/.well-known/oauth-protected-resource",
        "/sse",  # SSE connections are public for tool discovery
    }

    class AuthMiddleware:
        """Lazy OAuth: all MCP traffic passes through. Auth is checked per-tool."""

        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] != "http":
                await self.app(scope, receive, send)
                return

            path = scope["path"]

            # Public paths — no processing needed
            if path in _PUBLIC_PATHS:
                await self.app(scope, receive, send)
                return

            headers = dict(scope.get("headers", []))

            # If a Bearer token is present, validate it and set context
            # so tool wrappers can check api_key_context later.
            auth_header = headers.get(b"authorization", b"").decode()
            if auth_header.lower().startswith("bearer "):
                token_info = oauth_service.validate_access_token(auth_header[7:].strip())
                if token_info:
                    api_key_context.set(token_info)

            # Let ALL /messages through — auth is enforced per-tool
            if path.startswith("/messages"):
                # Extract session_id from query string for session-based auth
                qs = scope.get("query_string", b"").decode()
                for part in qs.split("&"):
                    if part.startswith("session_id="):
                        sid = part.split("=", 1)[1]
                        session_id_context.set(sid)
                        # If this session was authenticated via the authenticate tool,
                        # set api_key_context so all tools work
                        if sid in _session_auth:
                            api_key_context.set(_session_auth[sid])
                        break
                await self.app(scope, receive, send)
                return

            # Non-MCP, non-public paths still require a token
            if api_key_context.get() is None:
                _public_override = os.getenv("OAUTH_PUBLIC_BASE_URL", "").rstrip("/")
                if _public_override:
                    _base = _public_override
                else:
                    _proto = "https" if headers.get(b"x-forwarded-proto", b"").decode() == "https" else scope.get("scheme", "http")
                    _host = headers.get(b"host", b"localhost").decode()
                    _base = f"{_proto}://{_host}"
                response = Response(
                    content='{"error":"unauthorized","error_description":"A valid OAuth 2.1 Bearer token is required"}',
                    status_code=401,
                    media_type="application/json",
                    headers={"WWW-Authenticate": f'Bearer realm="Customer Success MCP", resource_metadata="{_base}/.well-known/oauth-protected-resource"'},
                )
                await response(scope, receive, send)
                return

            await self.app(scope, receive, send)

    # ── Wrap every tool to enforce OAuth at the MCP level ────────────────────
    # Instead of returning HTTP 401 (which trips circuit breakers), each tool
    # checks api_key_context and returns a friendly tool-level error that the
    # model can understand and act on.

    _oauth_base = os.getenv("OAUTH_PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")

    def _wrap_tool_with_auth(original_fn):
        """Wrap a tool function to require auth (Bearer or session) before execution."""
        import functools

        def _is_authed():
            """Check if current request has auth via Bearer token OR session auth."""
            if api_key_context.get() is not None:
                return True
            # Check session auth using the MCP server session object.
            try:
                ctx = mcp.get_context()
                session_key = id(ctx.session)
                if session_key in _session_auth:
                    info = _session_auth[session_key]
                    # Check TTL
                    if time.time() - info.get('created_at', 0) > _SESSION_AUTH_TTL:
                        del _session_auth[session_key]
                        logger.info(f"[LAZY-AUTH] Session {session_key} expired (TTL)")
                        return False
                    # Check weakref liveness
                    ref = info.get('session_ref')
                    if ref is not None and ref() is None:
                        del _session_auth[session_key]
                        logger.info(f"[LAZY-AUTH] Session {session_key} expired (object GC'd)")
                        return False
                    return True
            except Exception:
                pass
            return False

        def _make_auth_error():
            """Generate an auth error with an auth_request_id linked to this session."""
            # Periodically clean up stale entries
            _cleanup_expired_auth()

            auth_request_id = secrets.token_urlsafe(16)
            try:
                ctx = mcp.get_context()
                session_obj = ctx.session
                session_key = id(session_obj)
                _pending_auth_requests[auth_request_id] = {
                    'session_key': session_key,
                    'session_ref': weakref.ref(session_obj),
                    'created_at': time.time(),
                }
            except Exception:
                pass
            sign_in_url = f"{_oauth_base}/authorize?auth_request_id={auth_request_id}"
            return {
                "success": False,
                "error": "authentication_required",
                "message": (
                    "🔐 Authentication is required before using this tool.\n\n"
                    f"Please ask the user to open this link to sign in:\n{sign_in_url}\n\n"
                    "Once they complete sign-in in the browser, their session will be "
                    "automatically activated. Just try the tool again after they confirm "
                    "they have signed in.\n\n"
                    "You can also call 'check_auth_status' to verify the session is ready."
                ),
            }

        @functools.wraps(original_fn)
        def sync_wrapper(*args, **kwargs):
            if not _is_authed():
                logger.info(f"[LAZY-AUTH] Tool '{original_fn.__name__}' blocked — no auth")
                return _make_auth_error()
            return original_fn(*args, **kwargs)

        @functools.wraps(original_fn)
        async def async_wrapper(*args, **kwargs):
            if not _is_authed():
                logger.info(f"[LAZY-AUTH] Tool '{original_fn.__name__}' blocked — no auth")
                return _make_auth_error()
            return await original_fn(*args, **kwargs)

        return async_wrapper if asyncio.iscoroutinefunction(original_fn) else sync_wrapper

    # Tools that work WITHOUT authentication
    _AUTH_EXEMPT_TOOLS = {'check_auth_status'}

    # Patch all registered tools
    if hasattr(mcp, '_tool_manager') and hasattr(mcp._tool_manager, '_tools'):
        for tool_name, tool_obj in mcp._tool_manager._tools.items():
            if tool_name in _AUTH_EXEMPT_TOOLS:
                logger.info(f"[LAZY-AUTH] Tool '{tool_name}' — exempt from auth (activation-based)")
            else:
                tool_obj.fn = _wrap_tool_with_auth(tool_obj.fn)
        logger.info(f"[LAZY-AUTH] Wrapped {len(mcp._tool_manager._tools)} tools with OAuth guard")

    # ── Assemble app ─────────────────────────────────────────────────────────
    app = mcp.sse_app()

    async def health_check(request: Request) -> JSONResponse:
        return JSONResponse({
            "status": "healthy",
            "service": "customer-success-mcp",
            "version": settings.server_version,
        })

    async def root(request: Request) -> JSONResponse:
        return JSONResponse({
            "service": "Customer Success MCP Server",
            "version": settings.server_version,
            "auth": "OAuth 2.1 + PKCE (Bearer token required)",
            "endpoints": {
                "sse": "/sse",
                "health": "/health",
                "oauth_metadata": "/.well-known/oauth-authorization-server",
                "authorize": "/authorize",
                "token": "/token",
                "register": "/register",
            },
        })

    app.routes.insert(0, Route("/", root))
    app.routes.insert(0, Route("/health", health_check))
    app.routes.insert(0, Route("/.well-known/oauth-authorization-server", oauth_server_metadata))
    app.routes.insert(0, Route("/.well-known/oauth-protected-resource",   oauth_protected_resource))
    app.routes.insert(0, Route("/register", oauth_register,  methods=["POST"]))
    app.routes.insert(0, Route("/token",    oauth_token,     methods=["POST"]))
    app.routes.insert(0, Route("/revoke",   oauth_revoke,    methods=["POST"]))
    app.routes.insert(0, Route("/complete-auth", oauth_complete_auth, methods=["POST"]))
    app.routes.insert(0, Route("/pkce-generate", oauth_pkce_generate, methods=["GET"]))
    app.routes.insert(0, Route("/authorize/callback", oauth_authorize_callback, methods=["GET"]))
    app.routes.insert(0, Route("/authorize", oauth_authorize, methods=["GET", "POST"]))

    app = AuthMiddleware(app)
    return app


if __name__ == "__main__":
    main()
