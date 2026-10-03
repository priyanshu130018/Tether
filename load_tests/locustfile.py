from locust import HttpUser, task, between


class TetherLoadUser(HttpUser):
    wait_time = between(0.5, 2.0)

    @task(5)
    def check_liveness(self):
        self.client.get("/health/live", name="GET /health/live")

    @task(3)
    def check_detailed_health(self):
        self.client.get("/health", name="GET /health")

    @task(2)
    def scrape_metrics(self):
        self.client.get("/metrics", name="GET /metrics")

    @task(1)
    def check_version(self):
        self.client.get("/api/version", name="GET /api/version")
