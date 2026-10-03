from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    REGISTRY,
    generate_latest,
)

# --- 1. HTTP Metrics (Low-Cardinality Labels) ---
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total count of HTTP requests processed by Tether API",
    ["method", "path", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency distribution in seconds",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

HTTP_REQUESTS_FAILED_TOTAL = Counter(
    "http_requests_failed_total",
    "Total count of HTTP requests resulting in 5xx server errors",
    ["method", "path", "error_type"],
)

# --- 2. Monitoring Probe Metrics ---
MONITORING_CHECKS_TOTAL = Counter(
    "monitoring_checks_total",
    "Total count of monitoring probe checks executed",
    ["protocol", "status"],
)

MONITORING_CHECKS_SUCCESS_TOTAL = Counter(
    "monitoring_checks_success_total",
    "Total count of successful monitoring probe checks",
    ["protocol"],
)

MONITORING_CHECKS_FAILURE_TOTAL = Counter(
    "monitoring_checks_failure_total",
    "Total count of failed monitoring probe checks",
    ["protocol", "error_type"],
)

MONITORING_CHECK_DURATION_SECONDS = Histogram(
    "monitoring_check_duration_seconds",
    "Monitoring probe round-trip latency in seconds",
    ["protocol"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0),
)

MONITORING_JOBS_TOTAL = Counter(
    "monitoring_jobs_total",
    "Total count of background monitoring jobs scheduled",
    ["task_type", "status"],
)

MONITORING_QUEUE_DELAY_SECONDS = Histogram(
    "monitoring_queue_delay_seconds",
    "Latency from job creation to worker execution start in seconds",
    ["task_type"],
    buckets=(0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

MONITORING_EXECUTION_DURATION_SECONDS = Histogram(
    "monitoring_execution_duration_seconds",
    "Total duration of probe check execution and persistence in seconds",
    ["protocol"],
    buckets=(0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

MONITORING_JOBS_FAILED_TOTAL = Counter(
    "monitoring_jobs_failed_total",
    "Total count of monitoring jobs ending in failure",
    ["task_type"],
)

MONITORING_JOBS_TIMED_OUT_TOTAL = Counter(
    "monitoring_jobs_timed_out_total",
    "Total count of monitoring jobs marked as timed out",
    ["task_type"],
)

# --- 3. Alert & Notification Metrics ---
ALERTS_CREATED_TOTAL = Counter(
    "alerts_created_total",
    "Total count of state transition alerts generated",
    ["event_type"],
)

ALERTS_SUPPRESSED_TOTAL = Counter(
    "alerts_suppressed_total",
    "Total count of alerts suppressed by cooldown or disabled rules",
    ["event_type"],
)

ALERTS_RECOVERED_TOTAL = Counter(
    "alerts_recovered_total",
    "Total count of recovery events detected",
)

NOTIFICATION_DELIVERIES_TOTAL = Counter(
    "notification_deliveries_total",
    "Total count of notification delivery attempts",
    ["channel_type", "status"],
)

NOTIFICATION_DELIVERY_FAILURES_TOTAL = Counter(
    "notification_delivery_failures_total",
    "Total count of failed notification dispatches",
    ["channel_type"],
)

NOTIFICATION_DELIVERY_DURATION_SECONDS = Histogram(
    "notification_delivery_duration_seconds",
    "Notification dispatch duration in seconds",
    ["channel_type"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# --- 4. Celery Worker Metrics ---
CELERY_TASKS_STARTED_TOTAL = Counter(
    "celery_tasks_started_total",
    "Total count of Celery tasks started",
    ["task_name"],
)

CELERY_TASKS_COMPLETED_TOTAL = Counter(
    "celery_tasks_completed_total",
    "Total count of Celery tasks successfully completed",
    ["task_name"],
)

CELERY_TASKS_FAILED_TOTAL = Counter(
    "celery_tasks_failed_total",
    "Total count of Celery tasks failed",
    ["task_name"],
)

CELERY_TASK_DURATION_SECONDS = Histogram(
    "celery_task_duration_seconds",
    "Celery task execution duration in seconds",
    ["task_name"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)


def get_prometheus_metrics() -> tuple[bytes, str]:
    """Generate latest Prometheus metrics payload and content type."""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
