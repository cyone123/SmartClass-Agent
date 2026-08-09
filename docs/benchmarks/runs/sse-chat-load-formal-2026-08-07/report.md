# Formal SSE performance baseline

- Generated: `2026-08-06T16:56:29.266289+00:00`
- Workload: authenticated non-RAG `/api/chat/stream` SSE, fixed normal-chat prompt.
- Matrix: 1/2/4/8 concurrent users × 3 independent 5-minute windows per mode.
- Resource sample: backend process once per second; p95/max are calculated per window and the table shows the worst window.

## Gate summary

- Formal gate: **FAIL**
- Required windows: 12 per mode (24 total); completed: 24

## Results

| Mode | Users | Windows | Requests | Failure rate | Full p50 range | Full p95 max | TTFT p95 max | WS max MB | Private max MB | CPU p95 % | Samples |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| mock | 1 | 3/3 | 2122 | 0% | 200–230 ms | 230 ms | 110 ms | 374.2 | 729.93 | 1.68 | 891 |
| mock | 2 | 3/3 | 4234 | 0% | 200–230 ms | 240 ms | 110 ms | 373.77 | 730 | 2.84 | 893 |
| mock | 4 | 3/3 | 7716 | 0% | 250–260 ms | 320 ms | 140 ms | 374.27 | 731.07 | 4.88 | 891 |
| mock | 8 | 3/3 | 10385 | 0% | 500–510 ms | 590 ms | 240 ms | 375.8 | 732.7 | 6.45 | 894 |
| live | 1 | 3/3 | 131 | 0% | 6000–6900 ms | 9800 ms | 2600 ms | 378.44 | 733.66 | 0.51 | 892 |
| live | 2 | 3/3 | 240 | 0% | 6600–7300 ms | 14000 ms | 2800 ms | 374.25 | 733.73 | 0.77 | 892 |
| live | 4 | 3/3 | 512 | 0% | 6500–6700 ms | 11000 ms | 2500 ms | 374.64 | 733.92 | 1.07 | 892 |
| live | 8 | 3/3 | 788 | 0.8883% | 6400–6700 ms | 135000 ms | 2900 ms | 379.16 | 737.49 | 1.8 | 892 |

## Observed error events

- `live` 8u: 7 request failures; 3× unknown|timeout|unknown|No streaming chunk received for 120.0s (model=deepseek-v4-flash, chunks_received=0). The connection may be alive at the TCP layer but is not producing content. Tune or disable via the `stream_chunk_timeout` constructor kwarg (set to None....

## Interpretation

The Mock mode keeps the HTTP/SSE/auth/orchestration path while replacing upstream model time with a deterministic local response. The live-vs-mock latency gap is therefore an attribution aid, not a claim that Mock reproduces model quality.

Error details are retained in `summary.json` using the benchmark harness's redacted error taxonomy. Raw prompts, credentials, tokens, and authorization headers are not part of the evidence.
