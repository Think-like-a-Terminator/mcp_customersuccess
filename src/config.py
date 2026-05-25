"""Configuration management for the Customer Success MCP Server."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Authentication
    jwt_secret_key: str = "dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    
    # PostgreSQL Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "customer_success"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    
    # SMTP Email Configuration (optional)
    smtp_host: Optional[str] = None
    smtp_port: int = 25
    smtp_from_email: str = "noreply@example.com"
    smtp_use_tls: bool = False
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    
    # AWS SES Configuration (optional)
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"
    ses_from_email: str = "noreply@example.com"
    
    # Server
    server_name: str = "customer-success-mcp"
    server_version: str = "0.1.0"

    # Slack Notifications (optional)
    slack_webhook_url: Optional[str] = None

    # Salesforce CRM Integration (optional)
    salesforce_username: Optional[str] = None
    salesforce_password: Optional[str] = None
    salesforce_security_token: Optional[str] = None
    salesforce_domain: str = "login"  # use "test" for sandboxes

    # HubSpot CRM Integration (optional)
    hubspot_api_key: Optional[str] = None

    @property
    def slack_configured(self) -> bool:
        """Check if Slack notifications are configured."""
        return bool(self.slack_webhook_url)

    @property
    def salesforce_configured(self) -> bool:
        """Check if Salesforce integration is configured."""
        return bool(self.salesforce_username and self.salesforce_password and self.salesforce_security_token)

    @property
    def hubspot_configured(self) -> bool:
        """Check if HubSpot integration is configured."""
        return bool(self.hubspot_api_key)

    @property
    def smtp_configured(self) -> bool:
        """Check if SMTP is configured (host must be set)."""
        return bool(self.smtp_host)
    
    @property
    def ses_configured(self) -> bool:
        """Check if AWS SES is configured (both key and secret must be set)."""
        return bool(self.aws_access_key_id and self.aws_secret_access_key)
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra environment variables
    )


# Global settings instance
settings = Settings()
