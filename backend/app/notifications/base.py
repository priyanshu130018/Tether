from abc import ABC, abstractmethod
from typing import Any
import re


def mask_sensitive_config(config: dict[str, Any] | None) -> dict[str, Any]:
    """
    Returns a copy of the configuration dictionary with sensitive fields masked.
    Masks passwords, tokens, secrets, API keys, and webhook URLs.
    """
    if not config:
        return {}

    masked = dict(config)
    sensitive_keys = {
        "password",
        "smtp_password",
        "pass",
        "token",
        "api_key",
        "apikey",
        "secret",
        "secret_token",
        "authorization",
        "auth_token",
    }

    for key, value in list(masked.items()):
        key_lower = key.lower()
        if key_lower in sensitive_keys or any(s in key_lower for s in ("secret", "password", "token", "auth")):
            if isinstance(value, str) and value:
                masked[key] = "********"
        elif "webhook_url" in key_lower or key_lower == "url":
            if isinstance(value, str) and value:
                # Mask secret webhook token part (e.g. Slack webhook tokens or URL query params)
                # For Slack: https://hooks.slack.com/services/T00/B00/XXXXX -> https://hooks.slack.com/services/***
                if "hooks.slack.com/services/" in value:
                    prefix = value.split("hooks.slack.com/services/")[0] + "hooks.slack.com/services/"
                    masked[key] = prefix + "***"
                elif "discord.com/api/webhooks/" in value:
                    prefix = value.split("discord.com/api/webhooks/")[0] + "discord.com/api/webhooks/"
                    masked[key] = prefix + "***"
                else:
                    # General masking for URLs with potential tokens/auth
                    masked[key] = re.sub(r"://([^@]+)@", "://***:***@", value)

    return masked


class BaseNotificationSender(ABC):
    """
    Abstract base class for notification channel senders.
    """

    @abstractmethod
    def send(self, config: dict[str, Any], event_data: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Send a notification to the target channel.

        Args:
            config: Channel configuration (e.g., SMTP settings, webhook URL).
            event_data: Notification payload containing event_type, target, timestamp, message, metadata.

        Returns:
            tuple of (success: bool, error_message: str | None)
        """
        pass
