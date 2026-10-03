import ipaddress
import logging
import socket
from typing import Any
from urllib.parse import urlparse
import httpx

from app.notifications.base import BaseNotificationSender

logger = logging.getLogger(__name__)

FORBIDDEN_HOSTS = {
    "localhost",
    "metadata.google.internal",
    "instance-data",
    "169.254.169.254",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
}


def validate_webhook_url(url: str, check_dns: bool = True) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme '{parsed.scheme}'. Only http and https are allowed.")
    if not parsed.netloc or not parsed.hostname:
        raise ValueError("Invalid URL: missing hostname or domain")

    hostname = parsed.hostname.lower()
    if hostname in FORBIDDEN_HOSTS:
        raise ValueError(f"SSRF protection: Request to restricted host/IP '{hostname}' is blocked.")

    # Direct IP literal check
    try:
        ip = ipaddress.ip_address(hostname)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ValueError(f"SSRF protection: Request to private/restricted IP address '{hostname}' is blocked.")
    except ValueError as exc:
        if "SSRF protection" in str(exc):
            raise
        # Not an IP literal; perform DNS resolution check if enabled
        if check_dns:
            try:
                addr_info = socket.getaddrinfo(hostname, None)
                for *_, sockaddr in addr_info:
                    ip_str = sockaddr[0]
                    resolved_ip = ipaddress.ip_address(ip_str)
                    if (
                        resolved_ip.is_private
                        or resolved_ip.is_loopback
                        or resolved_ip.is_link_local
                        or resolved_ip.is_multicast
                        or resolved_ip.is_reserved
                        or resolved_ip.is_unspecified
                    ):
                        raise ValueError(
                            f"SSRF protection: Domain '{hostname}' resolves to restricted IP address '{ip_str}'."
                        )
            except socket.gaierror:
                # In offline/mocked environments or unresolvable test domains, skip DNS check
                pass


class WebhookNotificationSender(BaseNotificationSender):
    """
    Generic HTTP Webhook notification sender.
    """

    def send(self, config: dict[str, Any], event_data: dict[str, Any]) -> tuple[bool, str | None]:
        url = config.get("url") or config.get("webhook_url")
        if not url:
            return False, "Missing webhook URL in configuration"

        try:
            validate_webhook_url(url)
        except ValueError as exc:
            return False, str(exc)

        headers = dict(config.get("headers") or {})
        headers.setdefault("Content-Type", "application/json")
        headers.setdefault("User-Agent", "Tether-Alert-Notifier/1.0")

        # Standard clean JSON payload for generic webhooks
        payload = {
            "event_type": event_data.get("event_type"),
            "event_id": event_data.get("event_id"),
            "target": {
                "id": event_data.get("target_id"),
                "name": event_data.get("target_name") or event_data.get("target", {}).get("name"),
                "host": event_data.get("target_host") or event_data.get("target", {}).get("host") or event_data.get("target", {}).get("hostname"),
                "protocol": event_data.get("protocol") or event_data.get("target", {}).get("protocol"),
            },
            "timestamp": event_data.get("timestamp"),
            "message": event_data.get("message"),
            "metadata": event_data.get("metadata") or {},
        }

        timeout = float(config.get("timeout", 10.0))

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, json=payload, headers=headers)
                if 200 <= response.status_code < 300:
                    logger.info("[WebhookSender] Successfully posted alert notification to %s", url)
                    return True, None
                else:
                    err = f"Webhook endpoint returned non-2xx status code {response.status_code}: {response.text[:200]}"
                    logger.warning("[WebhookSender] %s", err)
                    return False, err
        except Exception as exc:
            err = f"Webhook request failed: {exc}"
            logger.warning("[WebhookSender] %s", err)
            return False, err
