"""In-memory data storage for the Customer Success MCP Server."""

from typing import Dict, List, Optional
from datetime import datetime
import uuid
from src.models import (
    CallToAction,
    HealthScore,
    RiskAlert,
    Priority,
    CTAStatus,
    HealthScoreStatus,
    RiskLevel,
)


class DataStore:
    """In-memory data store for customer success data."""
    
    def __init__(self):
        """Initialize data storage."""
        self.ctas: Dict[str, CallToAction] = {}
        self.health_scores: Dict[str, HealthScore] = {}
        self.risk_alerts: Dict[str, RiskAlert] = {}
        
        # Initialize with some sample data
        self._initialize_sample_data()
    
    def _initialize_sample_data(self):
        """Add some sample data for demonstration."""
        # Sample CTA
        cta_id = str(uuid.uuid4())
        self.ctas[cta_id] = CallToAction(
            id=cta_id,
            account_id="acct-001",
            title="Conduct Quarterly Business Review",
            description="Schedule and conduct QBR with key stakeholders to review product adoption and ROI",
            priority=Priority.HIGH,
            status=CTAStatus.OPEN,
            owner="csm@example.com",
            tags=["qbr", "high-touch"],
        )
        
        # Sample Health Score
        self.health_scores["acct-001"] = HealthScore(
            account_id="acct-001",
            overall_score=75.0,
            status=HealthScoreStatus.GOOD,
            metrics=[
                {"name": "product_usage", "value": 80.0, "weight": 0.3, "last_updated": datetime.now()},
                {"name": "engagement_score", "value": 70.0, "weight": 0.3, "last_updated": datetime.now()},
                {"name": "support_tickets", "value": 75.0, "weight": 0.2, "last_updated": datetime.now()},
                {"name": "payment_history", "value": 85.0, "weight": 0.2, "last_updated": datetime.now()},
            ],
            trend="stable",
        )
        
        # Sample Risk Alert
        alert_id = str(uuid.uuid4())
        self.risk_alerts[alert_id] = RiskAlert(
            id=alert_id,
            account_id="acct-002",
            risk_level=RiskLevel.MEDIUM,
            risk_factors=[
                "Decreased product usage (30% drop in 30 days)",
                "No executive engagement in 60 days",
                "Support ticket volume increased",
            ],
            impact_score=65.0,
            recommended_actions=[
                "Schedule executive business review",
                "Conduct product usage analysis",
                "Review support ticket themes",
            ],
        )
    
    # Call to Action methods
    def create_cta(self, cta: CallToAction) -> CallToAction:
        """Create a new CTA."""
        if not cta.id:
            cta.id = str(uuid.uuid4())
        cta.created_at = datetime.now()
        cta.updated_at = datetime.now()
        self.ctas[cta.id] = cta
        return cta
    
    def get_cta(self, cta_id: str) -> Optional[CallToAction]:
        """Get a CTA by ID."""
        return self.ctas.get(cta_id)
    
    def list_ctas(
        self,
        account_id: Optional[str] = None,
        status: Optional[CTAStatus] = None,
        priority: Optional[Priority] = None,
    ) -> List[CallToAction]:
        """List CTAs with optional filters."""
        ctas = list(self.ctas.values())
        
        if account_id:
            ctas = [cta for cta in ctas if cta.account_id == account_id]
        if status:
            ctas = [cta for cta in ctas if cta.status == status]
        if priority:
            ctas = [cta for cta in ctas if cta.priority == priority]
        
        return ctas
    
    def update_cta(self, cta_id: str, updates: dict) -> Optional[CallToAction]:
        """Update a CTA."""
        if cta_id not in self.ctas:
            return None
        
        cta = self.ctas[cta_id]
        for key, value in updates.items():
            if hasattr(cta, key):
                setattr(cta, key, value)
        
        cta.updated_at = datetime.now()
        return cta
    
    def delete_cta(self, cta_id: str) -> bool:
        """Delete a CTA."""
        if cta_id in self.ctas:
            del self.ctas[cta_id]
            return True
        return False
    
    # Health Score methods
    def set_health_score(self, health_score: HealthScore) -> HealthScore:
        """Set or update health score for an account."""
        health_score.last_calculated = datetime.now()
        self.health_scores[health_score.account_id] = health_score
        return health_score
    
    def get_health_score(self, account_id: str) -> Optional[HealthScore]:
        """Get health score for an account."""
        return self.health_scores.get(account_id)
    
    def list_health_scores(
        self,
        status: Optional[HealthScoreStatus] = None,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
    ) -> List[HealthScore]:
        """List health scores with optional filters."""
        scores = list(self.health_scores.values())
        
        if status:
            scores = [s for s in scores if s.status == status]
        if min_score is not None:
            scores = [s for s in scores if s.overall_score >= min_score]
        if max_score is not None:
            scores = [s for s in scores if s.overall_score <= max_score]
        
        return scores
    
    # Risk Alert methods
    def create_risk_alert(self, alert: RiskAlert) -> RiskAlert:
        """Create a new risk alert."""
        if not alert.id:
            alert.id = str(uuid.uuid4())
        alert.created_at = datetime.now()
        self.risk_alerts[alert.id] = alert
        return alert
    
    def get_risk_alert(self, alert_id: str) -> Optional[RiskAlert]:
        """Get a risk alert by ID."""
        return self.risk_alerts.get(alert_id)
    
    def list_risk_alerts(
        self,
        account_id: Optional[str] = None,
        risk_level: Optional[RiskLevel] = None,
        acknowledged: Optional[bool] = None,
    ) -> List[RiskAlert]:
        """List risk alerts with optional filters."""
        alerts = list(self.risk_alerts.values())
        
        if account_id:
            alerts = [a for a in alerts if a.account_id == account_id]
        if risk_level:
            alerts = [a for a in alerts if a.risk_level == risk_level]
        if acknowledged is not None:
            alerts = [a for a in alerts if a.acknowledged == acknowledged]
        
        return alerts
    
    def acknowledge_risk_alert(
        self,
        alert_id: str,
        acknowledged_by: str,
        notes: Optional[str] = None,
    ) -> Optional[RiskAlert]:
        """Acknowledge a risk alert."""
        if alert_id not in self.risk_alerts:
            return None
        
        alert = self.risk_alerts[alert_id]
        alert.acknowledged = True
        alert.acknowledged_by = acknowledged_by
        alert.acknowledged_at = datetime.now()
        if notes:
            alert.notes = notes
        
        return alert


# Global data store instance
data_store = DataStore()
