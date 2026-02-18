"""PostgreSQL storage for MCP server tools (CTAs, Health Scores, Risk Alerts)."""

from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid
import json
from src.db_service import DatabaseService
from src.models import (
    CallToAction,
    HealthScore,
    RiskAlert,
    Priority,
    CTAStatus,
    HealthScoreStatus,
    RiskLevel,
    HealthScoreMetric,
)


class MCPStorage:
    """PostgreSQL storage for MCP server data."""
    
    def __init__(self):
        """Initialize PostgreSQL storage."""
        self.db = DatabaseService()
    
    # ========================================================================
    # CALL TO ACTIONS
    # ========================================================================
    
    def create_cta(self, cta: CallToAction) -> CallToAction:
        """Create a new CTA in PostgreSQL."""
        if not cta.id:
            cta.id = str(uuid.uuid4())
        
        query = """
            INSERT INTO call_to_actions (
                id, account_id, title, description, priority, status,
                owner, due_date, tags, created_at, updated_at
            ) VALUES (
                %(id)s, %(account_id)s, %(title)s, %(description)s, 
                %(priority)s, %(status)s, %(owner)s, %(due_date)s, %(tags)s,
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            RETURNING id, created_at, updated_at
        """
        
        result = self.db.execute_query(
            query,
            {
                "id": cta.id,
                "account_id": cta.account_id,
                "title": cta.title,
                "description": cta.description,
                "priority": cta.priority.value,
                "status": cta.status.value,
                "owner": cta.owner,
                "due_date": cta.due_date,
                "tags": cta.tags or [],
            },
            fetch_results=True
        )
        
        if result.get("success") and result.get("results"):
            cta.created_at = result["results"][0]['created_at']
            cta.updated_at = result["results"][0]['updated_at']
        
        return cta
    
    def get_cta(self, cta_id: str) -> Optional[CallToAction]:
        """Get a CTA by ID."""
        query = """
            SELECT id, account_id, title, description, priority, status,
                   owner, due_date, completed_at, tags, created_at, updated_at
            FROM call_to_actions
            WHERE id = %(cta_id)s
        """
        
        result = self.db.execute_query(query, {"cta_id": cta_id}, fetch_results=True)
        
        if not result.get("success") or not result.get("results"):
            return None
        
        row = result["results"][0]
        return CallToAction(
            id=row['id'],
            account_id=row['account_id'],
            title=row['title'],
            description=row['description'],
            priority=Priority(row['priority']),
            status=CTAStatus(row['status']),
            owner=row['owner'],
            due_date=row['due_date'],
            completed_at=row['completed_at'],
            tags=row['tags'] or [],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )
    
    def list_ctas(
        self,
        account_id: Optional[str] = None,
        status: Optional[CTAStatus] = None,
        priority: Optional[Priority] = None,
    ) -> List[CallToAction]:
        """List CTAs with optional filters."""
        conditions = []
        params = {}
        
        if account_id:
            conditions.append("account_id = %(account_id)s")
            params["account_id"] = account_id
        
        if status:
            conditions.append("status = %(status)s")
            params["status"] = status.value
        
        if priority:
            conditions.append("priority = %(priority)s")
            params["priority"] = priority.value
        
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        
        query = f"""
            SELECT id, account_id, title, description, priority, status,
                   owner, due_date, completed_at, tags, created_at, updated_at
            FROM call_to_actions
            {where_clause}
            ORDER BY created_at DESC
        """
        
        result = self.db.execute_query(query, params, fetch_results=True)
        
        if not result.get("success") or not result.get("results"):
            return []
        
        return [
            CallToAction(
                id=row['id'],
                account_id=row['account_id'],
                title=row['title'],
                description=row['description'],
                priority=Priority(row['priority']),
                status=CTAStatus(row['status']),
                owner=row['owner'],
                due_date=row['due_date'],
                completed_at=row['completed_at'],
                tags=row['tags'] or [],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
            for row in result["results"]
        ]
    
    def update_cta(self, cta_id: str, updates: dict) -> Optional[CallToAction]:
        """Update a CTA."""
        # Build dynamic update query
        update_fields = []
        params = {"cta_id": cta_id}
        
        for key, value in updates.items():
            if key in ['status', 'priority', 'title', 'description', 'owner', 'due_date', 'completed_at', 'tags']:
                if key in ['status', 'priority'] and hasattr(value, 'value'):
                    value = value.value
                update_fields.append(f"{key} = %({key})s")
                params[key] = value
        
        if not update_fields:
            return self.get_cta(cta_id)
        
        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        
        query = f"""
            UPDATE call_to_actions
            SET {', '.join(update_fields)}
            WHERE id = %(cta_id)s
            RETURNING id
        """
        
        result = self.db.execute_query(query, params, fetch_results=True)
        
        if not result.get("success") or not result.get("results"):
            return None
        
        return self.get_cta(cta_id)
    
    def delete_cta(self, cta_id: str) -> bool:
        """Delete a CTA."""
        query = "DELETE FROM call_to_actions WHERE id = %(cta_id)s RETURNING id"
        result = self.db.execute_query(query, {"cta_id": cta_id}, fetch_results=True)
        return result.get("success", False) and bool(result.get("results"))
    
    # ========================================================================
    # HEALTH SCORES
    # ========================================================================
    
    def set_health_score(self, health_score: HealthScore) -> HealthScore:
        """Set or update health score for an account."""
        # Convert metrics to JSON
        metrics_json = json.dumps([
            {
                "name": m.name,
                "value": m.value,
                "weight": m.weight,
                "last_updated": m.last_updated.isoformat() if isinstance(m.last_updated, datetime) else m.last_updated
            }
            for m in (health_score.metrics or [])
        ])
        
        query = """
            INSERT INTO health_scores (
                account_id, overall_score, status, metrics, trend, last_calculated
            ) VALUES (
                %(account_id)s, %(overall_score)s, %(status)s, %(metrics)s, %(trend)s, CURRENT_TIMESTAMP
            )
            ON CONFLICT (account_id) DO UPDATE SET
                overall_score = EXCLUDED.overall_score,
                status = EXCLUDED.status,
                metrics = EXCLUDED.metrics,
                trend = EXCLUDED.trend,
                last_calculated = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id, last_calculated, created_at, updated_at
        """
        
        result = self.db.execute_query(
            query,
            {
                "account_id": health_score.account_id,
                "overall_score": health_score.overall_score,
                "status": health_score.status.value,
                "metrics": metrics_json,
                "trend": health_score.trend or 'stable',
            },
            fetch_results=True
        )
        
        if result.get("success") and result.get("results"):
            health_score.last_calculated = result["results"][0]['last_calculated']
        
        return health_score
    
    def get_health_score(self, account_id: str) -> Optional[HealthScore]:
        """Get health score for an account."""
        query = """
            SELECT account_id, overall_score, status, metrics, trend, last_calculated
            FROM health_scores
            WHERE account_id = %(account_id)s
        """
        
        result = self.db.execute_query(query, {"account_id": account_id}, fetch_results=True)
        
        if not result.get("success") or not result.get("results"):
            return None
        
        row = result["results"][0]
        
        # Parse metrics JSON
        metrics_data = row['metrics'] if isinstance(row['metrics'], list) else json.loads(row['metrics'])
        metrics = []
        for m in metrics_data:
            last_updated = m.get('last_updated')
            if isinstance(last_updated, str):
                last_updated = datetime.fromisoformat(last_updated)
            metrics.append(HealthScoreMetric(
                name=m['name'],
                value=m['value'],
                weight=m['weight'],
                last_updated=last_updated
            ))
        
        return HealthScore(
            account_id=row['account_id'],
            overall_score=float(row['overall_score']),
            status=HealthScoreStatus(row['status']),
            metrics=metrics,
            trend=row['trend'],
            last_calculated=row['last_calculated']
        )
    
    def list_health_scores(
        self,
        status: Optional[HealthScoreStatus] = None,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
    ) -> List[HealthScore]:
        """List health scores with optional filters."""
        conditions = []
        params = {}
        
        if status:
            conditions.append("status = %(status)s")
            params["status"] = status.value
        
        if min_score is not None:
            conditions.append("overall_score >= %(min_score)s")
            params["min_score"] = min_score
        
        if max_score is not None:
            conditions.append("overall_score <= %(max_score)s")
            params["max_score"] = max_score
        
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        
        query = f"""
            SELECT account_id, overall_score, status, metrics, trend, last_calculated
            FROM health_scores
            {where_clause}
            ORDER BY overall_score DESC
        """
        
        result = self.db.execute_query(query, params, fetch_results=True)
        
        if not result.get("success") or not result.get("results"):
            return []
        
        health_scores = []
        for row in result["results"]:
            metrics_data = row['metrics'] if isinstance(row['metrics'], list) else json.loads(row['metrics'])
            metrics = []
            for m in metrics_data:
                last_updated = m.get('last_updated')
                if isinstance(last_updated, str):
                    last_updated = datetime.fromisoformat(last_updated)
                metrics.append(HealthScoreMetric(
                    name=m['name'],
                    value=m['value'],
                    weight=m['weight'],
                    last_updated=last_updated
                ))
            
            health_scores.append(HealthScore(
                account_id=row['account_id'],
                overall_score=float(row['overall_score']),
                status=HealthScoreStatus(row['status']),
                metrics=metrics,
                trend=row['trend'],
                last_calculated=row['last_calculated']
            ))
        
        return health_scores
    
    # ========================================================================
    # RISK ALERTS
    # ========================================================================
    
    def create_risk_alert(self, alert: RiskAlert) -> RiskAlert:
        """Create a new risk alert."""
        if not alert.id:
            alert.id = str(uuid.uuid4())
        
        query = """
            INSERT INTO risk_alerts (
                id, account_id, risk_level, risk_factors, impact_score,
                recommended_actions, created_at, updated_at
            ) VALUES (
                %(id)s, %(account_id)s, %(risk_level)s, %(risk_factors)s,
                %(impact_score)s, %(recommended_actions)s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            RETURNING id, created_at, updated_at
        """
        
        result = self.db.execute_query(
            query,
            {
                "id": alert.id,
                "account_id": alert.account_id,
                "risk_level": alert.risk_level.value,
                "risk_factors": alert.risk_factors or [],
                "impact_score": alert.impact_score,
                "recommended_actions": alert.recommended_actions or [],
            },
            fetch_results=True
        )
        
        if result.get("success") and result.get("results"):
            alert.created_at = result["results"][0]['created_at']
        
        return alert
    
    def get_risk_alert(self, alert_id: str) -> Optional[RiskAlert]:
        """Get a risk alert by ID."""
        query = """
            SELECT id, account_id, risk_level, risk_factors, impact_score,
                   recommended_actions, acknowledged, acknowledged_by, acknowledged_at,
                   notes, created_at, updated_at
            FROM risk_alerts
            WHERE id = %(alert_id)s
        """
        
        result = self.db.execute_query(query, {"alert_id": alert_id}, fetch_results=True)
        
        if not result.get("success") or not result.get("results"):
            return None
        
        row = result["results"][0]
        return RiskAlert(
            id=row['id'],
            account_id=row['account_id'],
            risk_level=RiskLevel(row['risk_level']),
            risk_factors=row['risk_factors'] or [],
            impact_score=float(row['impact_score']) if row['impact_score'] else None,
            recommended_actions=row['recommended_actions'] or [],
            acknowledged=row['acknowledged'],
            acknowledged_by=row['acknowledged_by'],
            acknowledged_at=row['acknowledged_at'],
            notes=row['notes'],
            created_at=row['created_at']
        )
    
    def list_risk_alerts(
        self,
        account_id: Optional[str] = None,
        risk_level: Optional[RiskLevel] = None,
        acknowledged: Optional[bool] = None,
    ) -> List[RiskAlert]:
        """List risk alerts with optional filters."""
        conditions = []
        params = {}
        
        if account_id:
            conditions.append("account_id = %(account_id)s")
            params["account_id"] = account_id
        
        if risk_level:
            conditions.append("risk_level = %(risk_level)s")
            params["risk_level"] = risk_level.value
        
        if acknowledged is not None:
            conditions.append("acknowledged = %(acknowledged)s")
            params["acknowledged"] = acknowledged
        
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        
        query = f"""
            SELECT id, account_id, risk_level, risk_factors, impact_score,
                   recommended_actions, acknowledged, acknowledged_by, acknowledged_at,
                   notes, created_at, updated_at
            FROM risk_alerts
            {where_clause}
            ORDER BY created_at DESC
        """
        
        result = self.db.execute_query(query, params, fetch_results=True)
        
        if not result.get("success") or not result.get("results"):
            return []
        
        return [
            RiskAlert(
                id=row['id'],
                account_id=row['account_id'],
                risk_level=RiskLevel(row['risk_level']),
                risk_factors=row['risk_factors'] or [],
                impact_score=float(row['impact_score']) if row['impact_score'] else None,
                recommended_actions=row['recommended_actions'] or [],
                acknowledged=row['acknowledged'],
                acknowledged_by=row['acknowledged_by'],
                acknowledged_at=row['acknowledged_at'],
                notes=row['notes'],
                created_at=row['created_at']
            )
            for row in result["results"]
        ]
    
    def acknowledge_risk_alert(
        self,
        alert_id: str,
        acknowledged_by: str,
        notes: Optional[str] = None,
    ) -> Optional[RiskAlert]:
        """Acknowledge a risk alert."""
        query = """
            UPDATE risk_alerts
            SET acknowledged = TRUE,
                acknowledged_by = %(acknowledged_by)s,
                acknowledged_at = CURRENT_TIMESTAMP,
                notes = COALESCE(%(notes)s, notes),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %(alert_id)s
            RETURNING id
        """
        
        result = self.db.execute_query(
            query,
            {
                "alert_id": alert_id,
                "acknowledged_by": acknowledged_by,
                "notes": notes,
            },
            fetch_results=True
        )
        
        if not result.get("success") or not result.get("results"):
            return None
        
        return self.get_risk_alert(alert_id)


# Global MCP storage instance
mcp_storage = MCPStorage()
