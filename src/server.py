"""Customer Success MCP Server - Main server implementation."""

import asyncio
import sys
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
from src.storage import data_store
from src.mcp_storage import mcp_storage
from src.api_key_service import APIKeyService

# Context variable to store API key info for current request
api_key_context: ContextVar[Optional[dict]] = ContextVar('api_key_context', default=None)
from src.db_service import db_service
from src.user_service import UserService

# Initialize services
user_service = UserService()

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
def authenticate(username: str, password: str) -> dict[str, Any]:
    """
    Authenticate a user and receive an access token.
    
    Default users (change passwords in production!):
    - username: admin, password: admin123 (full access)
    - username: csm, password: csm123 (read/write access)
    
    Args:
        username: Username for authentication
        password: Password for authentication
    
    Returns:
        Authentication token and user information
    """
    user = authenticate_user(username, password)
    if not user:
        return {
            "success": False,
            "error": "Invalid username or password",
        }
    
    access_token = create_access_token(
        data={"sub": user.username, "scopes": user.scopes}
    )
    
    return {
        "success": True,
        "access_token": access_token,
        "token_type": "bearer",
        "user": user.dict(),
        "expires_in": settings.access_token_expire_minutes * 60,
    }


@mcp.tool()
def register_user(
    admin_email: str,
    admin_password: str,
    username: str,
    email: str,
    password: str,
    full_name: Optional[str] = None,
    admin: bool = False,
    send_verification_email: bool = True,
) -> dict[str, Any]:
    """
    Register a new user account (admin only).
    
    ⚠️ ADMIN ONLY: Requires admin email and password to authenticate.
    Admin credentials are verified against the database.
    
    Creates a new user account and optionally sends a verification email.
    Verification emails are sent via SMTP or AWS SES if configured.
    If no email provider is configured, registration still succeeds but
    no verification email is sent.
    
    Args:
        admin_email: Admin's email address (must exist in users table with admin=true)
        admin_password: Admin's password
        username: Desired username (must be unique, min 3 characters)
        email: Email address (must be unique and valid)
        password: Password (min 8 characters)
        full_name: Optional full name
        admin: Whether to grant admin privileges to the new user (default False)
        send_verification_email: Whether to send a verification email (default True,
            requires SMTP or AWS SES to be configured)
    
    Returns:
        Registration status, user information, and verification email status
    
    Example:
        register_user(
            admin_email="admin@company.com",
            admin_password="admin_password",
            username="newuser",
            email="newuser@company.com",
            password="userpassword123",
            full_name="New User",
            admin=False
        )
    """
    try:
        from src.config import settings

        # Verify admin credentials against Cloud SQL database
        admin_check = user_service.verify_admin(admin_email, admin_password)
        if not admin_check["success"]:
            return {
                "success": False,
                "error": admin_check.get("error", "Admin authentication failed")
            }
        
        result = user_service.register_user(
            username=username,
            email=email,
            password=password,
            full_name=full_name,
            admin=admin,
            send_verification_email=send_verification_email,
        )
        
        return {
            "success": True,
            "registered_by": admin_check.get("username", admin_email),
            **result,
        }
    
    except ValueError as e:
        return {
            "success": False,
            "error": str(e),
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Registration failed: {str(e)}",
        }


@mcp.tool()
def update_user(
    admin_email: str,
    admin_password: str,
    username: str,
    email: Optional[str] = None,
    password: Optional[str] = None,
    full_name: Optional[str] = None,
    disabled: Optional[bool] = None,
    admin: Optional[bool] = None,
) -> dict[str, Any]:
    """
    Update an existing user's attributes (admin only).
    
    ⚠️ ADMIN ONLY: Requires admin email and password to authenticate.
    Admin credentials are verified against the Cloud SQL database.
    
    Only provide the fields you want to update. Fields not provided will remain unchanged.
    
    Args:
        admin_email: Admin's email address (must exist in users table with admin=true)
        admin_password: Admin's password
        username: Username of the user to update (required - identifies the user)
        email: New email address (optional)
        password: New password - will be hashed (optional)
        full_name: New full name (optional)
        disabled: Set disabled status - true to disable, false to enable (optional)
        admin: Set admin status - true to grant admin, false to revoke (optional)
    
    Returns:
        Update status and updated user information
    
    Example:
        update_user(
            admin_email="admin@company.com",
            admin_password="admin_password",
            username="existinguser",
            email="newemail@company.com",
            disabled=False,
            admin=True
        )
    """
    try:
        # Verify admin credentials against Cloud SQL database
        admin_check = user_service.verify_admin(admin_email, admin_password)
        if not admin_check["success"]:
            return {
                "success": False,
                "error": admin_check.get("error", "Admin authentication failed")
            }
        
        result = user_service.update_user(
            username=username,
            email=email,
            password=password,
            full_name=full_name,
            disabled=disabled,
            admin=admin,
        )
        
        return {
            "success": True,
            "updated_by": admin_check.get("username", admin_email),
            **result,
        }
    
    except ValueError as e:
        return {
            "success": False,
            "error": str(e),
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Update failed: {str(e)}",
        }


@mcp.tool()
def verify_user_email(token: str) -> dict[str, Any]:
    """
    Verify a user's email address using the token from their verification email.
    
    Args:
        token: Verification token from the email
    
    Returns:
        Verification status
    """
    try:
        result = user_service.verify_email(token)
        
        return {
            "success": True,
            **result,
        }
    
    except ValueError as e:
        return {
            "success": False,
            "error": str(e),
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Verification failed: {str(e)}",
        }


@mcp.tool()
def resend_verification_email(email: str) -> dict[str, Any]:
    """
    Resend verification email to a user.
    
    Useful if the original verification email was not received or expired.
    Requires SMTP or AWS SES to be configured.
    
    Args:
        email: User's email address
    
    Returns:
        Status of the email resend
    """
    try:
        from src.email_service import email_service
        
        if not email_service.is_configured:
            return {
                "success": False,
                "error": "No email provider configured. Set SMTP_HOST or AWS credentials.",
            }
        
        # Generate new token via user_service
        result = user_service.resend_verification_email(email)
        
        if not result.get("success"):
            return result
        
        # Send the email with the new token
        token = result.get("token")
        username = result.get("username", "User")
        
        send_result = email_service.send_verification_email(
            to_email=email,
            username=username,
            verification_token=token,
        )
        
        return {
            "success": send_result["success"],
            "message": "Verification email sent! Check your inbox." if send_result["success"] else "Failed to send email.",
            "provider": send_result.get("provider"),
            "error": send_result.get("error"),
        }
    
    except ValueError as e:
        return {
            "success": False,
            "error": str(e),
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to resend verification email: {str(e)}",
        }


@mcp.tool()
def list_users(
    admin_email: str,
    admin_password: str,
    admin_only: bool = False
) -> dict[str, Any]:
    """
    List all registered users (admin only).
    
    ⚠️ ADMIN ONLY: Requires admin email and password to authenticate.
    Admin credentials are verified against the Cloud SQL database.
    Passwords are never returned in the response.
    
    Args:
        admin_email: Admin's email address (must exist in users table with admin=true)
        admin_password: Admin's password
        admin_only: If True, only return users with admin privileges
    
    Returns:
        List of users with their information
    
    Example:
        list_users(admin_email="admin@company.com", admin_password="your_password")
        list_users(admin_email="admin@company.com", admin_password="your_password", admin_only=True)
    """
    try:
        # Verify admin credentials against Cloud SQL database
        admin_check = user_service.verify_admin(admin_email, admin_password)
        if not admin_check["success"]:
            return {
                "success": False,
                "error": admin_check.get("error", "Admin authentication failed")
            }
        
        users = user_service.list_users(admin_only=admin_only)
        
        return {
            "success": True,
            "count": len(users),
            "users": users,
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to list users: {str(e)}",
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
        
        return {
            "success": True,
            "alert": created_alert.dict(),
            "message": f"Risk alert created with ID: {created_alert.id}",
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
    username: str,
    query: str,
    fetch_results: bool = True,
    max_rows: int = 10000,
) -> dict[str, Any]:
    """
    Execute a READ-ONLY SQL query against the PostgreSQL database.
    
    Ask for the username as an argument as only registered users in the database can use this tool.
    
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
        username: Username of registered user
        query: SQL query to execute (SELECT statements only)
        fetch_results: Whether to return query results (should be True for SELECT)
        max_rows: Maximum rows to return (default: 10000, max: 10000)
    
    Returns:
        Query results with success status, row count, and data
    """
    from src.config import settings
    
    # Verify user exists in database - registered users only
    user_data = user_service.get_user_by_username(username)
    if not user_data:
        return {
            "success": False,
            "error": f"User '{username}' not found. Only registered users can query the database.",
        }
    
    # Check if user is disabled
    if user_data.get("disabled", False):
        return {
            "success": False,
            "error": f"User '{username}' is disabled.",
        }
    
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
# API KEY MANAGEMENT TOOLS
# ============================================================================

@mcp.tool()
def generate_api_key(
    admin_email: str,
    admin_password: str,
    name: str,
    description: str = "",
    expires_in_days: Optional[int] = None
) -> dict[str, Any]:
    """
    Generate a new API key for authentication (admin only).
    
    ⚠️ ADMIN ONLY: Requires admin email and password to authenticate.
    Admin credentials are verified against the Cloud SQL database.
    ⚠️ IMPORTANT: The plaintext API key is only shown once during creation.
    Store it securely - you won't be able to retrieve it again.
    
    Args:
        admin_email: Admin's email address (must exist in users table with admin=true)
        admin_password: Admin's password
        name: Friendly name for the API key (e.g., "LibreChat Production")
        description: Optional description of the key's purpose
        expires_in_days: Number of days until expiration (optional, null = never expires)
    
    Returns:
        API key information including the plaintext key (shown only once)
    
    Example:
        generate_api_key(
            admin_email="admin@company.com",
            admin_password="your_password",
            name="LibreChat Production",
            description="API key for LibreChat on Google Cloud Run",
            expires_in_days=365
        )
    """
    try:
        # Verify admin credentials against Cloud SQL database
        admin_check = user_service.verify_admin(admin_email, admin_password)
        if not admin_check["success"]:
            return {
                "success": False,
                "error": admin_check.get("error", "Admin authentication failed")
            }
        
        created_by = admin_check.get("username", admin_email)
        
        api_key_service = APIKeyService()
        result = api_key_service.create_api_key(
            name=name,
            description=description,
            created_by=created_by,
            expires_in_days=expires_in_days
        )
        
        return {
            "success": True,
            "message": "API key created successfully",
            "api_key": result["api_key"],  # ⚠️ Only shown once!
            "key_id": result["id"],
            "key_prefix": result["key_prefix"],
            "name": name,
            "created_by": created_by,
            "expires_at": result.get("expires_at"),
            "warning": "⚠️ Store this API key securely! You won't be able to retrieve it again."
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to generate API key: {str(e)}",
            "error_type": type(e).__name__,
        }


@mcp.tool()
def list_api_keys(
    admin_email: str,
    admin_password: str,
    created_by: Optional[str] = None
) -> dict[str, Any]:
    """
    List all API keys (admin only).
    
    ⚠️ ADMIN ONLY: Requires admin email and password to authenticate.
    Admin credentials are verified against the Cloud SQL database.
    
    Note: The plaintext API key values are never returned for security.
    Only the key prefix (first 8 characters) is shown for identification.
    
    Args:
        admin_email: Admin's email address (must exist in users table with admin=true)
        admin_password: Admin's password
        created_by: Filter by creator username (optional, shows all if not specified)
    
    Returns:
        List of API keys with metadata (excluding plaintext values)
    
    Example:
        list_api_keys(admin_email="admin@company.com", admin_password="your_password")
        list_api_keys(admin_email="admin@company.com", admin_password="your_password", created_by="admin")
    """
    try:
        # Verify admin credentials against Cloud SQL database
        admin_check = user_service.verify_admin(admin_email, admin_password)
        if not admin_check["success"]:
            return {
                "success": False,
                "error": admin_check.get("error", "Admin authentication failed")
            }
        
        api_key_service = APIKeyService()
        result = api_key_service.list_api_keys(created_by=created_by)
        
        if result["success"]:
            keys = result["keys"]
            return {
                "success": True,
                "count": len(keys),
                "keys": keys,
                "message": f"Found {len(keys)} API key(s)"
            }
        else:
            return result
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to list API keys: {str(e)}",
            "error_type": type(e).__name__,
        }


@mcp.tool()
def revoke_api_key(
    admin_email: str,
    admin_password: str,
    key_id: int
) -> dict[str, Any]:
    """
    Revoke (deactivate) an API key without deleting it (admin only).
    
    ⚠️ ADMIN ONLY: Requires admin email and password to authenticate.
    Admin credentials are verified against the Cloud SQL database.
    
    Revoked keys will fail authentication immediately but remain in the database
    for audit purposes. This is safer than deleting keys.
    
    Args:
        admin_email: Admin's email address (must exist in users table with admin=true)
        admin_password: Admin's password
        key_id: The ID of the API key to revoke
    
    Returns:
        Confirmation of revocation
    
    Example:
        revoke_api_key(admin_email="admin@company.com", admin_password="your_password", key_id=1)
    """
    try:
        # Verify admin credentials against Cloud SQL database
        admin_check = user_service.verify_admin(admin_email, admin_password)
        if not admin_check["success"]:
            return {
                "success": False,
                "error": admin_check.get("error", "Admin authentication failed")
            }
        
        api_key_service = APIKeyService()
        result = api_key_service.revoke_api_key(key_id=key_id)
        
        if result["success"]:
            return {
                "success": True,
                "message": f"API key {key_id} has been revoked",
                "key_id": key_id,
                "revoked_at": result.get("revoked_at")
            }
        else:
            return result
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to revoke API key: {str(e)}",
            "error_type": type(e).__name__,
        }


@mcp.tool()
def delete_api_key(
    admin_email: str,
    admin_password: str,
    key_id: int
) -> dict[str, Any]:
    """
    Permanently delete an API key from the database (admin only).
    
    ⚠️ ADMIN ONLY: Requires admin email and password to authenticate.
    Admin credentials are verified against the Cloud SQL database.
    ⚠️ WARNING: This action cannot be undone. Consider using revoke_api_key instead
    to keep audit history.
    
    Args:
        admin_email: Admin's email address (must exist in users table with admin=true)
        admin_password: Admin's password
        key_id: The ID of the API key to delete
    
    Returns:
        Confirmation of deletion
    
    Example:
        delete_api_key(admin_email="admin@company.com", admin_password="your_password", key_id=1)
    """
    try:
        # Verify admin credentials against Cloud SQL database
        admin_check = user_service.verify_admin(admin_email, admin_password)
        if not admin_check["success"]:
            return {
                "success": False,
                "error": admin_check.get("error", "Admin authentication failed")
            }
        
        api_key_service = APIKeyService()
        result = api_key_service.delete_api_key(key_id=key_id)
        
        if result["success"]:
            return {
                "success": True,
                "message": f"API key {key_id} has been permanently deleted",
                "key_id": key_id
            }
        else:
            return result
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to delete API key: {str(e)}",
            "error_type": type(e).__name__,
        }


def main():
    """For testing purposes. Run the MCP server in stdio mode."""
    mcp.run(transport="stdio")


def create_sse_app():
    """
    Create an SSE (Server-Sent Events) app for HTTP/cloud deployment.
    Use this for deploying to Google Cloud Run or other cloud platforms.
    """
    from starlette.responses import JSONResponse, Response
    from starlette.routing import Route
    
    # Configure transport security to allow Cloud Run host
    # Disable DNS rebinding protection for cloud deployment
    # In production, you should set allowed_hosts to your specific domain
    import os
    from mcp.server.transport_security import TransportSecuritySettings
    
    # Check if we're running in Cloud Run
    cloud_run_service_url = os.environ.get('K_SERVICE')  # Cloud Run sets this
    if cloud_run_service_url or os.environ.get('PORT'):
        # In Cloud Run: disable DNS rebinding protection or allow all hosts
        # For production, set allowed_hosts to your specific Cloud Run URL
        mcp.settings.transport_security = TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        )
    
    # Initialize API key service
    api_key_service = APIKeyService()
    
    # API Key Middleware - using raw ASGI to avoid issues with streaming responses
    class APIKeyMiddleware:
        def __init__(self, app):
            self.app = app
        
        async def __call__(self, scope, receive, send):
            if scope["type"] != "http":
                await self.app(scope, receive, send)
                return
            
            # Get path
            path = scope["path"]
            
            # Skip authentication for health check, root, and messages
            if path in ["/health", "/"] or path.startswith("/messages"):
                await self.app(scope, receive, send)
                return
            
            # For SSE endpoint, check API key
            headers = dict(scope.get("headers", []))
            api_key = headers.get(b"x-api-key", b"").decode()
            
            if not api_key:
                response = Response(
                    content='{"error": "Missing X-API-Key header"}',
                    status_code=401,
                    media_type="application/json"
                )
                await response(scope, receive, send)
                return
            
            # Validate API key
            key_info = api_key_service.validate_api_key(api_key)
            if not key_info:
                response = Response(
                    content='{"error": "Invalid or expired API key"}',
                    status_code=401,
                    media_type="application/json"
                )
                await response(scope, receive, send)
                return
            
            # Store key info in context variable for use in tools
            api_key_context.set(key_info)
            
            # Call the app
            await self.app(scope, receive, send)
    
    # Get the MCP SSE app
    app = mcp.sse_app()
    
    # Add health check endpoint for Cloud Run
    async def health_check(request):
        return JSONResponse({
            "status": "healthy",
            "service": "customer-success-mcp",
            "version": settings.server_version
        })
    
    # Add root endpoint
    async def root(request):
        return JSONResponse({
            "service": "Customer Success MCP Server",
            "version": settings.server_version,
            "endpoints": {
                "sse": "/sse",
                "messages": "/messages",
                "health": "/health"
            }
        })
    
    # Add routes to the app BEFORE wrapping with middleware
    app.routes.insert(0, Route("/", root))
    app.routes.insert(0, Route("/health", health_check))
    
    # Wrap app with API key middleware AFTER adding routes
    app = APIKeyMiddleware(app)
    
    return app


if __name__ == "__main__":
    main()
