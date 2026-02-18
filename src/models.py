"""Data models for the Customer Success MCP Server."""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class Priority(str, Enum):
    """Priority levels for CTAs and alerts."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CTAStatus(str, Enum):
    """Status of a Call to Action."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DISMISSED = "dismissed"


class HealthScoreStatus(str, Enum):
    """Health score status categories."""
    EXCELLENT = "excellent"
    GOOD = "good"
    AT_RISK = "at_risk"
    CRITICAL = "critical"


class RiskLevel(str, Enum):
    """Risk level for accounts."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# Call to Action Models
class CallToAction(BaseModel):
    """Call to Action data model."""
    id: str = Field(..., description="Unique identifier for the CTA")
    account_id: str = Field(..., description="Account associated with this CTA")
    title: str = Field(..., description="Title of the CTA")
    description: str = Field(..., description="Detailed description of the action needed")
    priority: Priority = Field(default=Priority.MEDIUM, description="Priority level")
    status: CTAStatus = Field(default=CTAStatus.OPEN, description="Current status")
    owner: Optional[str] = Field(None, description="Assigned owner/CSM")
    due_date: Optional[datetime] = Field(None, description="Due date for completion")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update timestamp")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


# Health Score Models
class HealthScoreMetric(BaseModel):
    """Individual health score metric."""
    name: str = Field(..., description="Metric name")
    value: float = Field(..., description="Metric value (0-100)")
    weight: float = Field(default=1.0, description="Weight in overall calculation")
    last_updated: Optional[datetime] = Field(default_factory=datetime.now, description="Last update time")


class HealthScore(BaseModel):
    """Account health score data model."""
    account_id: str = Field(..., description="Account identifier")
    overall_score: float = Field(..., description="Overall health score (0-100)", ge=0, le=100)
    status: HealthScoreStatus = Field(..., description="Health status category")
    metrics: List[HealthScoreMetric] = Field(default_factory=list, description="Individual metrics")
    trend: str = Field(default="stable", description="Trend: improving, declining, or stable")
    last_calculated: datetime = Field(default_factory=datetime.now, description="Calculation timestamp")
    notes: Optional[str] = Field(None, description="Additional notes or context")


# Risk Alert Models
class RiskAlert(BaseModel):
    """Account risk alert data model."""
    id: str = Field(..., description="Unique alert identifier")
    account_id: str = Field(..., description="Account identifier")
    risk_level: RiskLevel = Field(..., description="Current risk level")
    risk_factors: List[str] = Field(default_factory=list, description="Identified risk factors")
    impact_score: float = Field(..., description="Potential impact (0-100)", ge=0, le=100)
    recommended_actions: List[str] = Field(default_factory=list, description="Recommended mitigation actions")
    created_at: datetime = Field(default_factory=datetime.now, description="Alert creation time")
    acknowledged: bool = Field(default=False, description="Whether alert has been acknowledged")
    acknowledged_by: Optional[str] = Field(None, description="Person who acknowledged")
    acknowledged_at: Optional[datetime] = Field(None, description="Acknowledgment timestamp")
    notes: Optional[str] = Field(None, description="Additional notes")


# Authentication Models
class User(BaseModel):
    """User authentication model."""
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    full_name: Optional[str] = Field(None, description="Full name")
    disabled: bool = Field(default=False, description="Whether user is disabled")
    scopes: List[str] = Field(default_factory=list, description="User permissions/scopes")


class Token(BaseModel):
    """Authentication token."""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")


class TokenData(BaseModel):
    """Token payload data."""
    username: Optional[str] = None
    scopes: List[str] = Field(default_factory=list)


# Report Job Models
    acknowledged_by: Optional[str] = Field(None, description="Person who acknowledged")
