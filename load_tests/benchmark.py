from pathlib import Path
import argparse
import asyncio
import statistics
import sys
import time
from typing import NamedTuple
import httpx

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class BenchmarkResult(NamedTuple):
    endpoint: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    requests_per_sec: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    avg_latency_ms: float


async def run_benchmark(
    base_url: str,
    path: str,
    method: str = "GET",
    token: str | None = None,
    concurrency: int = 20,
    total_requests: int = 200,
    app_instance=None,
) -> BenchmarkResult:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    latencies: list[float] = []
    success_count = 0
    failure_count = 0

    semaphore = asyncio.Semaphore(concurrency)

    transport = httpx.ASGITransport(app=app_instance) if app_instance else None

    async with httpx.AsyncClient(transport=transport, base_url=base_url, headers=headers, timeout=10.0) as client:
        async def make_request():
            nonlocal success_count, failure_count
            async with semaphore:
                start = time.perf_counter()
                try:
                    if method == "GET":
                        resp = await client.get(path)
                    else:
                        resp = await client.post(path)
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    latencies.append(elapsed_ms)
                    if resp.status_code < 400:
                        success_count += 1
                    else:
                        failure_count += 1
                except Exception:
                    failure_count += 1

        overall_start = time.perf_counter()
        tasks = [make_request() for _ in range(total_requests)]
        await asyncio.gather(*tasks)
        total_time = time.perf_counter() - overall_start

    rps = total_requests / total_time if total_time > 0 else 0.0
    sorted_latencies = sorted(latencies) if latencies else [0.0]

    def percentile(p: float) -> float:
        if not sorted_latencies:
            return 0.0
        k = (len(sorted_latencies) - 1) * (p / 100.0)
        f = int(k)
        c = min(f + 1, len(sorted_latencies) - 1)
        d = k - f
        return sorted_latencies[f] * (1 - d) + sorted_latencies[c] * d

    return BenchmarkResult(
        endpoint=path,
        total_requests=total_requests,
        successful_requests=success_count,
        failed_requests=failure_count,
        requests_per_sec=round(rps, 2),
        p50_ms=round(percentile(50), 2),
        p95_ms=round(percentile(95), 2),
        p99_ms=round(percentile(99), 2),
        avg_latency_ms=round(statistics.mean(sorted_latencies), 2) if sorted_latencies else 0.0,
    )


async def main():
    parser = argparse.ArgumentParser(description="Tether Load Benchmark")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of Tether API")
    parser.add_argument("--concurrency", type=int, default=25, help="Concurrent request workers")
    parser.add_argument("--requests", type=int, default=250, help="Total requests per endpoint")
    parser.add_argument("--in-process", action="store_true", help="Run benchmark directly in-process against FastAPI app")
    args = parser.parse_args()

    app_instance = None
    if args.in_process:
        from app.main import app
        app_instance = app

    print("=" * 75)
    print(f"Starting Tether API Benchmark ({'In-Process ASGI' if args.in_process else args.url})")
    print(f"Concurrency: {args.concurrency} | Total Requests per Endpoint: {args.requests}")
    print("=" * 75)

    endpoints = [
        "/health/live",
        "/health",
        "/api/version",
        "/metrics",
    ]

    for ep in endpoints:
        res = await run_benchmark(
            base_url=args.url,
            path=ep,
            concurrency=args.concurrency,
            total_requests=args.requests,
            app_instance=app_instance,
        )
        print(f"\nEndpoint: {res.endpoint}")
        print(f"  Requests: {res.total_requests} (Success: {res.successful_requests}, Failed: {res.failed_requests})")
        print(f"  Throughput: {res.requests_per_sec} req/sec")
        print(f"  Latencies -> Avg: {res.avg_latency_ms}ms | p50: {res.p50_ms}ms | p95: {res.p95_ms}ms | p99: {res.p99_ms}ms")

    print("\n" + "=" * 75)
    print("Benchmark complete.")


if __name__ == "__main__":
    asyncio.run(main())
