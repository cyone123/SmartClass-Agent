# Main graph simplification A/B evidence

This deterministic Windows run compares orchestration depth using 20 repetitions and a fixed 10 ms async delay per model call. It contains only aggregate scenario labels, call counts, and latency proxies; no prompt, completion, metadata, memory, attachment, user identifier, object key, URL, or host path is retained.

| Scenario | Legacy calls | Simplified calls | Visible milestone | Legacy median | Simplified median |
|---|---:|---:|---|---:|---:|
| Ordinary chat | 2 | 1 | First token | 31.339 ms | 15.694 ms |
| Memory-assisted chat | 2 | 2 | First token | 30.982 ms | 31.220 ms |
| First incomplete teaching request | 3 | 2 | Clarification | 46.670 ms | 31.359 ms |
| Clarification turn | 2 | 1 | Clarification | 31.038 ms | 15.716 ms |
| Complete teaching request | 2 | 2 | Metadata approval | 31.092 ms | 31.160 ms |

The evidence confirms the intended call-depth reduction for ordinary chat and subsequent clarification turns. Memory-assisted chat and a complete first teaching request retain two calls because their second round is functional rather than redundant. The small negative deltas in equal-depth rows are scheduler noise, not a regression claim.

Reproduce from `backend/`:

```powershell
python -m tests.benchmarks.main_graph_orchestration_ab --repeats 20 --delay-ms 10
```

This is a deterministic orchestration proxy, not a live-provider performance baseline. Production TTFT must still be measured separately with the SSE load benchmark before making provider-latency claims.
