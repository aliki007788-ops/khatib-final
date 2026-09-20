from prometheus_client import Counter, Histogram, Gauge


HTTP_REQUESTS_TOTAL = Counter(
    "khatib_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    "khatib_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "path"],
)

AI_REQUESTS_TOTAL = Counter(
    "khatib_ai_requests_total",
    "AI requests",
    ["task_type", "provider", "status"],
)

AI_REQUEST_DURATION = Histogram(
    "khatib_ai_request_duration_seconds",
    "AI request duration",
    ["task_type", "provider"],
)

PAYMENT_REQUESTS_TOTAL = Counter(
    "khatib_payment_requests_total",
    "Payment transactions",
    ["provider", "status"],
)

QUEUE_JOBS_TOTAL = Counter(
    "khatib_queue_jobs_total",
    "Queue jobs",
    ["job_type", "status"],
)

ACTIVE_WORKER_JOBS = Gauge(
    "khatib_active_worker_jobs",
    "Currently active worker jobs",
)
