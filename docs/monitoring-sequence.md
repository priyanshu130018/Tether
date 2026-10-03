# Tether — Monitoring & Probe Execution Sequence

This document details the turn-by-turn sequence diagram and execution flow for periodic network monitoring, probe execution, database persistence, and failure recovery.

---

## 1. Scheduled Monitoring Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    participant Beat as Celery Beat Scheduler
    participant Redis as Redis Queue / Lock Store
    participant Worker as Celery Worker
    participant DB as PostgreSQL Database
    participant Target as Monitored Target Endpoint
    participant Alert as Alert Engine

    loop Every Scheduler Tick (e.g. 5s)
        Beat->>DB: Query targets WHERE enabled=True AND next_check_at <= NOW()
        DB-->>Beat: List of eligible targets
        Beat->>DB: Advance next_check_at = NOW() + interval_seconds
        Beat->>Redis: Enqueue run_monitoring_check(target_id, job_id)
    end

    Redis->>Worker: Dequeue monitoring job
    Worker->>Redis: SET tether:lock:target:{id} NX EX=ttl (Acquire Lock)
    alt Lock Already Held
        Worker-->>Redis: Lock denied -> Discard duplicate job
    else Lock Acquired
        Worker->>DB: Verify target still exists & enabled
        Worker->>Target: Execute Network Probe (TCP / HTTP / HTTPS / DNS)
        
        alt Target Responds Successfully
            Target-->>Worker: Connection established / HTTP 200 / DNS Record
            Worker->>DB: INSERT INTO monitoring_results (status=UP, latency_ms)
            Worker->>DB: UPDATE targets SET status=UP, consecutive_failures=0, consecutive_successes+=1
            Worker->>Alert: evaluate_target_alerts(target, result)
        else Target Fails / Times Out
            Target-->>Worker: Socket timeout / Connection refused / 5xx error
            Worker->>DB: INSERT INTO monitoring_results (status=DOWN, error_type, latency_ms=NULL)
            Worker->>DB: UPDATE targets SET status=DOWN, consecutive_failures+=1, consecutive_successes=0
            Worker->>Alert: evaluate_target_alerts(target, result)
        end
        
        Worker->>Redis: DEL tether:lock:target:{id} (Release Lock)
    end
```

---

## 2. Step-by-Step Execution Lifecycle

1. **Scheduling Query**: Celery Beat runs periodic dispatcher tasks. It scans PostgreSQL for enabled targets due for inspection (`next_check_at <= now`).
2. **Interval Advance**: Before task enqueueing, Beat advances `next_check_at` to prevent repeated scheduling in the subsequent tick.
3. **Queue Ingestion**: Monitoring jobs enter the Redis FIFO queue.
4. **Concurrency Safety**:
   - The worker attempts an atomic `SET key val NX EX 30` in Redis.
   - If another worker is currently checking that same target, the task terminates immediately with zero duplicate network impact.
5. **Protocol Strategy Execution**:
   - Probes operate with a strict non-blocking timeout ($1.0\text{s} - 30.0\text{s}$).
   - Socket connections and HTTP sessions use ephemeral connection pooling to avoid socket exhaustion (`TIME_WAIT`).
6. **Persistence & Metrics**:
   - Every probe result is committed to `monitoring_results` with high-resolution latency timestamps.
   - Target state counters (`consecutive_failures`, `consecutive_successes`) are updated atomically.
   - Queue wait time ($\Delta t_{\text{queue}}$) and probe execution duration ($\Delta t_{\text{exec}}$) are recorded in Prometheus histograms.
7. **Alert Evaluation**: The alert engine evaluates the updated target status against configured rules.
