"""Email service supporting SMTP and AWS SES for sending emails."""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any

from src.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Unified email service with SMTP and AWS SES support.
    
    Priority order:
    1. SMTP (if SMTP_HOST is configured) — works with MailHog for local dev
    2. AWS SES (if AWS credentials are configured)
    3. Disabled (logs a warning, no email sent)
    """
    
    def __init__(self):
        """Initialize email service and detect available provider."""
        self._provider = self._detect_provider()
        logger.info(f"EmailService initialized with provider: {self._provider}")
    
    def _detect_provider(self) -> str:
        """Detect which email provider is available."""
        if settings.smtp_configured:
            return "smtp"
        if settings.ses_configured:
            return "ses"
        return "none"
    
    @property
    def is_configured(self) -> bool:
        """Check if any email provider is available."""
        return self._provider != "none"
    
    @property
    def provider(self) -> str:
        """Return the active email provider name."""
        return self._provider
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        from_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send an email using the configured provider.
        
        Args:
            to_email: Recipient email address
            subject: Email subject line
            body_html: HTML email body
            body_text: Plain text fallback (auto-generated from HTML if not provided)
            from_email: Override sender address (uses configured default if not provided)
        
        Returns:
            Dict with success status and provider info
        """
        if self._provider == "smtp":
            return self._send_via_smtp(to_email, subject, body_html, body_text, from_email)
        elif self._provider == "ses":
            return self._send_via_ses(to_email, subject, body_html, body_text, from_email)
        else:
            logger.warning(f"No email provider configured. Email to {to_email} not sent.")
            return {
                "success": False,
                "provider": "none",
                "error": "No email provider configured. Set SMTP_HOST or AWS credentials.",
            }
    
    def _send_via_smtp(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        from_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send email via SMTP (works with MailHog, Gmail, etc.)."""
        sender = from_email or settings.smtp_from_email
        
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = to_email
            
            # Attach plain text version
            if body_text:
                msg.attach(MIMEText(body_text, "plain"))
            
            # Attach HTML version
            msg.attach(MIMEText(body_html, "html"))
            
            # Connect and send
            if settings.smtp_use_tls:
                server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
            
            # Authenticate if credentials provided
            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            
            server.sendmail(sender, [to_email], msg.as_string())
            server.quit()
            
            logger.info(f"Email sent via SMTP to {to_email}: {subject}")
            return {
                "success": True,
                "provider": "smtp",
                "to": to_email,
                "subject": subject,
            }
            
        except Exception as e:
            logger.error(f"SMTP send failed: {e}")
            return {
                "success": False,
                "provider": "smtp",
                "error": f"SMTP send failed: {str(e)}",
            }
    
    def _send_via_ses(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        from_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send email via AWS SES."""
        sender = from_email or settings.ses_from_email
        
        try:
            import boto3
            
            client = boto3.client(
                "ses",
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
            )
            
            body = {"Html": {"Data": body_html, "Charset": "UTF-8"}}
            if body_text:
                body["Text"] = {"Data": body_text, "Charset": "UTF-8"}
            
            response = client.send_email(
                Source=sender,
                Destination={"ToAddresses": [to_email]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": body,
                },
            )
            
            message_id = response.get("MessageId", "unknown")
            logger.info(f"Email sent via SES to {to_email}: {subject} (MessageId: {message_id})")
            return {
                "success": True,
                "provider": "ses",
                "to": to_email,
                "subject": subject,
                "message_id": message_id,
            }
            
        except ImportError:
            logger.error("boto3 not installed — cannot use AWS SES")
            return {
                "success": False,
                "provider": "ses",
                "error": "boto3 package not installed. Install with: pip install boto3",
            }
        except Exception as e:
            logger.error(f"SES send failed: {e}")
            return {
                "success": False,
                "provider": "ses",
                "error": f"SES send failed: {str(e)}",
            }
    
    def send_verification_email(
        self,
        to_email: str,
        username: str,
        verification_token: str,
        base_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a user verification email.
        
        Args:
            to_email: Recipient email address
            username: The user's username
            verification_token: The verification token
            base_url: Optional base URL for the verification link
        
        Returns:
            Dict with send status
        """
        if not base_url:
            base_url = "https://customer-success-mcp.example.com"
        
        verification_url = f"{base_url}/verify?token={verification_token}"
        
        subject = "Verify Your Customer Success MCP Account"
        
        body_html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px;">
                <h2 style="color: #333;">Welcome to Customer Success MCP! 🎉</h2>
                <p>Hello <strong>{username}</strong>,</p>
                <p>Thank you for registering. Please verify your email address by clicking the button below:</p>
                <p style="text-align: center; margin: 30px 0;">
                    <a href="{verification_url}" 
                       style="background-color: #007bff; color: white; padding: 12px 24px; 
                              text-decoration: none; border-radius: 4px; font-weight: bold;">
                        Verify Email Address
                    </a>
                </p>
                <p style="color: #666; font-size: 14px;">
                    Or copy and paste this link into your browser:<br>
                    <code style="background: #e9ecef; padding: 2px 6px; border-radius: 3px;">
                        {verification_url}
                    </code>
                </p>
                <hr style="border: 1px solid #dee2e6; margin: 20px 0;">
                <p style="color: #999; font-size: 12px;">
                    This link will expire in 24 hours. If you didn't create this account, 
                    please ignore this email.
                </p>
            </div>
        </body>
        </html>
        """
        
        body_text = f"""
Hello {username},

Thank you for registering with Customer Success MCP Server!

Please verify your email address by visiting:
{verification_url}

This link will expire in 24 hours.

If you didn't create this account, please ignore this email.

Best regards,
Customer Success MCP Team
        """.strip()
        
        return self.send_email(
            to_email=to_email,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
        )


# Global email service instance
email_service = EmailService()
