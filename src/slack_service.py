"""Slack notification service for Customer Success MCP Server.

Sends notifications to a Slack channel via Incoming Webhooks when high-priority
events occur (e.g. a high-risk alert is created for an account).

Configuration:
    Set SLACK_WEBHOOK_URL in your environment to enable.
    Create a Slack app at https://api.slack.com/apps and add an Incoming Webhook.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_RISK_LEVEL_EMOJI = {
    "high":   "🔴",
    "medium": "🟡",
    "low":    "🟢",
    "none":   "⚪",
}

_RISK_LEVEL_COLOR = {
    "high":   "#E53935",
    "medium": "#FB8C00",
    "low":    "#43A047",
    "none":   "#9E9E9E",
}


class SlackService:
    """Sends notifications to Slack via Incoming Webhooks."""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url
        self._client = None

    @property
    def is_configured(self) -> bool:
        return bool(self.webhook_url)

    def _get_client(self):
        """Lazily initialize the slack_sdk WebhookClient."""
        if self._client is None:
            try:
                from slack_sdk.webhook import WebhookClient  # type: ignore
                self._client = WebhookClient(self.webhook_url)
            except ImportError:
                raise RuntimeError(
                    "slack_sdk is not installed. "
                    "Run: pip install slack-sdk"
                )
        return self._client

    def notify_risk_alert(
        self,
        account_id: str,
        risk_level: str,
        risk_factors: list[str],
        impact_score: float,
        recommended_actions: list[str],
        alert_id: str,
    ) -> dict:
        """
        Post a risk alert notification to Slack.

        Args:
            account_id: Account identifier
            risk_level: Risk level (none/low/medium/high)
            risk_factors: List of identified risk factors
            impact_score: Impact score 0-100
            recommended_actions: Recommended mitigation steps
            alert_id: Alert UUID for reference

        Returns:
            dict with success status
        """
        if not self.is_configured:
            return {"success": False, "error": "Slack webhook not configured"}

        try:
            client = self._get_client()
            emoji = _RISK_LEVEL_EMOJI.get(risk_level.lower(), "⚪")
            color = _RISK_LEVEL_COLOR.get(risk_level.lower(), "#9E9E9E")

            factors_text = "\n".join(f"• {f}" for f in risk_factors) if risk_factors else "_None specified_"
            actions_text = "\n".join(f"• {a}" for a in recommended_actions) if recommended_actions else "_None specified_"

            response = client.send(
                text=f"{emoji} New {risk_level.upper()} risk alert for account `{account_id}`",
                attachments=[
                    {
                        "color": color,
                        "blocks": [
                            {
                                "type": "header",
                                "text": {
                                    "type": "plain_text",
                                    "text": f"{emoji} {risk_level.upper()} Risk Alert — {account_id}",
                                },
                            },
                            {
                                "type": "section",
                                "fields": [
                                    {
                                        "type": "mrkdwn",
                                        "text": f"*Account ID*\n`{account_id}`",
                                    },
                                    {
                                        "type": "mrkdwn",
                                        "text": f"*Impact Score*\n{impact_score:.0f}/100",
                                    },
                                ],
                            },
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f"*Risk Factors*\n{factors_text}",
                                },
                            },
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f"*Recommended Actions*\n{actions_text}",
                                },
                            },
                            {
                                "type": "context",
                                "elements": [
                                    {
                                        "type": "mrkdwn",
                                        "text": f"Alert ID: `{alert_id}`  |  Customer Success MCP",
                                    }
                                ],
                            },
                        ],
                    }
                ],
            )

            if response.status_code == 200:
                logger.info("Slack notification sent for alert %s", alert_id)
                return {"success": True}
            else:
                logger.warning("Slack webhook returned %s: %s", response.status_code, response.body)
                return {"success": False, "error": f"Slack returned HTTP {response.status_code}"}

        except Exception as exc:
            logger.error("Failed to send Slack notification: %s", exc)
            return {"success": False, "error": str(exc)}


def _make_slack_service() -> SlackService:
    """Factory that reads config at import time."""
    from src.config import settings
    return SlackService(webhook_url=settings.slack_webhook_url)


slack_service = _make_slack_service()
