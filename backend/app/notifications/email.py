import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from app.notifications.base import BaseNotificationSender

logger = logging.getLogger(__name__)


class EmailNotificationSender(BaseNotificationSender):
    """
    SMTP Email notification sender.
    """

    def send(self, config: dict[str, Any], event_data: dict[str, Any]) -> tuple[bool, str | None]:
        smtp_host = config.get("smtp_host") or config.get("host")
        if not smtp_host:
            return False, "Missing SMTP host in configuration"

        smtp_port = int(config.get("smtp_port") or config.get("port") or 587)
        username = config.get("username") or config.get("user")
        password = config.get("password") or config.get("pass")
        from_email = config.get("from_email") or config.get("from_address") or "alerts@tether.local"

        recipients_raw = config.get("to_emails") or config.get("to_email") or config.get("recipients") or []
        if isinstance(recipients_raw, str):
            to_emails = [e.strip() for e in recipients_raw.split(",") if e.strip()]
        elif isinstance(recipients_raw, list):
            to_emails = [str(e).strip() for e in recipients_raw if str(e).strip()]
        else:
            to_emails = []

        if not to_emails:
            return False, "Missing recipient email(s) in configuration"

        use_tls = config.get("use_tls", True)
        use_ssl = config.get("use_ssl", False)
        timeout = float(config.get("timeout", 10.0))

        event_type = event_data.get("event_type", "ALERT")
        target_name = event_data.get("target_name") or event_data.get("target", {}).get("name", "Unknown Target")
        target_host = event_data.get("target_host") or event_data.get("target", {}).get("host") or event_data.get("target", {}).get("hostname", "")
        target_protocol = event_data.get("protocol") or event_data.get("target", {}).get("protocol", "TCP")
        message = event_data.get("message", "No description provided")
        timestamp = event_data.get("timestamp", "")
        extra = event_data.get("metadata") or {}

        subject = f"[Tether Alert] [{event_type}] {target_name} ({target_protocol.upper()}://{target_host})"

        body_lines = [
            f"Tether Monitoring Alert: {event_type}",
            "=" * 40,
            f"Target:               {target_name}",
            f"Host / Endpoint:      {target_protocol.upper()}://{target_host}",
            f"Event Type:           {event_type}",
            f"Timestamp:            {timestamp}",
            f"Message:              {message}",
        ]
        if "consecutive_failures" in extra:
            body_lines.append(f"Consecutive Failures: {extra['consecutive_failures']}")
        if "error_type" in extra and extra["error_type"]:
            body_lines.append(f"Error Type:           {extra['error_type']}")
        if "latency_ms" in extra and extra["latency_ms"] is not None:
            body_lines.append(f"Latency:              {extra['latency_ms']} ms")

        body_text = "\n".join(body_lines)

        msg = MIMEMultipart()
        msg["From"] = from_email
        msg["To"] = ", ".join(to_emails)
        msg["Subject"] = subject
        msg.attach(MIMEText(body_text, "plain"))

        try:
            client_cls = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
            with client_cls(smtp_host, smtp_port, timeout=timeout) as server:
                if use_tls and not use_ssl:
                    server.starttls()
                if username and password:
                    server.login(username, password)
                server.sendmail(from_email, to_emails, msg.as_string())

            logger.info("[EmailSender] Successfully sent alert email to %s", to_emails)
            return True, None
        except Exception as exc:
            err = f"SMTP delivery failed to {to_emails}: {exc}"
            logger.warning("[EmailSender] %s", err)
            return False, err
