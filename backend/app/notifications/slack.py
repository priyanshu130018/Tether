import logging
from typing import Any
import httpx

from app.notifications.base import BaseNotificationSender

logger = logging.getLogger(__name__)


class SlackNotificationSender(BaseNotificationSender):
    """
    Slack Incoming Webhook notification sender.
    """

    def send(self, config: dict[str, Any], event_data: dict[str, Any]) -> tuple[bool, str | None]:
        webhook_url = config.get("webhook_url") or config.get("url")
        if not webhook_url:
            return False, "Missing Slack webhook_url in configuration"

        if not (webhook_url.startswith("http://") or webhook_url.startswith("https://")):
            return False, "Invalid Slack webhook URL scheme (must be http or https)"

        event_type = event_data.get("event_type", "ALERT")
        target_name = event_data.get("target_name") or event_data.get("target", {}).get("name", "Unknown Target")
        target_host = event_data.get("target_host") or event_data.get("target", {}).get("host") or event_data.get("target", {}).get("hostname", "")
        target_protocol = (event_data.get("protocol") or event_data.get("target", {}).get("protocol", "TCP")).upper()
        message = event_data.get("message", "No description provided")
        timestamp = event_data.get("timestamp", "")
        extra = event_data.get("metadata") or {}

        is_outage = event_type == "OUTAGE"
        icon = "🔴" if is_outage else "🟢"
        header_text = f"{icon} Tether Alert: {event_type} - {target_name}"

        fields = [
            {"type": "mrkdwn", "text": f"*Target:*\n`{target_name}`"},
            {"type": "mrkdwn", "text": f"*Endpoint:*\n`{target_protocol}://{target_host}`"},
            {"type": "mrkdwn", "text": f"*Status:*\n{event_type}"},
            {"type": "mrkdwn", "text": f"*Time:*\n{timestamp}"},
        ]
        if "consecutive_failures" in extra:
            fields.append({"type": "mrkdwn", "text": f"*Consecutive Failures:*\n{extra['consecutive_failures']}"})
        if "latency_ms" in extra and extra["latency_ms"] is not None:
            fields.append({"type": "mrkdwn", "text": f"*Latency:*\n{extra['latency_ms']} ms"})

        payload = {
            "text": f"{icon} [{event_type}] {target_name} ({target_protocol}://{target_host}): {message}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": header_text[:150],
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "fields": fields[:10],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Details:*\n{message}",
                    },
                },
            ],
        }

        timeout = float(config.get("timeout", 10.0))

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(webhook_url, json=payload)
                if response.status_code == 200:
                    logger.info("[SlackSender] Successfully delivered alert notification to Slack")
                    return True, None
                else:
                    err = f"Slack webhook returned status {response.status_code}: {response.text[:200]}"
                    logger.warning("[SlackSender] %s", err)
                    return False, err
        except Exception as exc:
            err = f"Slack webhook request failed: {exc}"
            logger.warning("[SlackSender] %s", err)
            return False, err
