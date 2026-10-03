import logging
from app.models import ChannelType
from app.notifications.base import BaseNotificationSender
from app.notifications.email import EmailNotificationSender
from app.notifications.slack import SlackNotificationSender
from app.notifications.webhook import WebhookNotificationSender

logger = logging.getLogger(__name__)


class NotificationRegistry:
    """
    Registry mapping channel types (EMAIL, SLACK, WEBHOOK) to sender strategy implementations.
    """

    def __init__(self) -> None:
        self._senders: dict[str, BaseNotificationSender] = {}

    def register(self, channel_type: str | ChannelType, sender: BaseNotificationSender) -> None:
        key = channel_type.value if hasattr(channel_type, "value") else str(channel_type).upper()
        self._senders[key] = sender

    def get(self, channel_type: str | ChannelType) -> BaseNotificationSender:
        key = channel_type.value if hasattr(channel_type, "value") else str(channel_type).upper()
        if key not in self._senders:
            raise ValueError(f"No notification sender registered for channel type '{key}'")
        return self._senders[key]

    def has(self, channel_type: str | ChannelType) -> bool:
        key = channel_type.value if hasattr(channel_type, "value") else str(channel_type).upper()
        return key in self._senders


default_notification_registry = NotificationRegistry()
default_notification_registry.register(ChannelType.EMAIL, EmailNotificationSender())
default_notification_registry.register(ChannelType.SLACK, SlackNotificationSender())
default_notification_registry.register(ChannelType.WEBHOOK, WebhookNotificationSender())
