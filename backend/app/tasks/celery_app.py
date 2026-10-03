from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "tether",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.monitoring", "app.tasks.alerts", "app.tasks.maintenance"],
)

celery_app.conf.update(
    task_default_queue=settings.celery_queue,
    task_routes={
        "app.tasks.monitoring.run_monitoring_check": {"queue": settings.celery_queue},
        "app.tasks.monitoring.run_tcp_check": {"queue": settings.celery_queue},
        "app.tasks.monitoring.schedule_due_targets": {"queue": settings.celery_queue},
        "app.tasks.alerts.deliver_alert_event": {"queue": settings.celery_queue},
        "app.tasks.alerts.send_test_notification": {"queue": settings.celery_queue},
        "app.tasks.maintenance.cleanup_old_data": {"queue": settings.celery_queue},
    },
    # Task Reliability & Graceful Recovery
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_time_limit=120,
    task_soft_time_limit=90,
    result_expires=86400,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    timezone="UTC",
    beat_schedule={
        "schedule-due-monitoring-checks": {
            "task": "app.tasks.monitoring.schedule_due_targets",
            "schedule": settings.scheduler_tick_interval_seconds,
            "options": {"queue": settings.celery_queue},
        },
        "daily-data-retention-cleanup": {
            "task": "app.tasks.maintenance.cleanup_old_data",
            "schedule": 86400.0,  # Run every 24 hours
            "options": {"queue": settings.celery_queue},
        },
    },
)

celery_app.autodiscover_tasks(["app.tasks"])
