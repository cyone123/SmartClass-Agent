# Formal SSE performance baseline

- Generated: `2026-08-06T15:42:43.460707+00:00`
- Workload: authenticated non-RAG `/api/chat/stream` SSE, fixed normal-chat prompt.
- Matrix: 1/2/4/8 concurrent users × 3 independent 5-minute windows per mode.
- Resource sample: backend process once per second; p95/max are calculated per window and the table shows the worst window.

## Gate summary

- Formal gate: **PASS**
- Required windows: 12 per mode; completed: 12

## Results

| Mode | Users | Windows | Requests | Failure rate | Full p50 range | Full p95 max | TTFT p95 max | WS max MB | Private max MB | CPU p95 % | Samples |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| mock | 1 | 3/3 | 2122 | 0% | 200–230 ms | 230 ms | 110 ms | 374.2 | 729.93 | 1.68 | 891 |
| mock | 2 | 3/3 | 4234 | 0% | 200–230 ms | 240 ms | 110 ms | 373.77 | 730 | 2.84 | 893 |
| mock | 4 | 3/3 | 7716 | 0% | 250–260 ms | 320 ms | 140 ms | 374.27 | 731.07 | 4.88 | 891 |
| mock | 8 | 3/3 | 10385 | 0% | 500–510 ms | 590 ms | 240 ms | 375.8 | 732.7 | 6.45 | 894 |

## Interpretation

The Mock mode keeps the HTTP/SSE/auth/orchestration path while replacing upstream model time with a deterministic local response. The live-vs-mock latency gap is therefore an attribution aid, not a claim that Mock reproduces model quality.

Error details are retained in `summary.json` using the benchmark harness's redacted error taxonomy. Raw prompts, credentials, tokens, and authorization headers are not part of the evidence.
