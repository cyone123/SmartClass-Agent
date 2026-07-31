# Benchmark Baseline: stage1-model-eval-2026-07-30

- Run mode: `mixed`
- Git commit: `961f007c9d2b976b7c7f3e6b1df1e27ceab6dda8`
- Repository dirty: `True`
- Source fingerprint: `sha256:f34d4e7a3830f427307691c89bcbbde9a85d6ab787f2855f3be45dc1533ae235`
- Dataset: `sha256:fc363adfca72397f2af3bdd4350d2e0ac6ed524f140154deb674a902a9487a53`
- Sample size: 24
- Pass rate: 95.83%
- Error rate: 0.00%
- Average score: 0.942

## Category metrics

| Category | Mode | Cases | Passed | Failed | Error | Pass rate | Avg score |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| context_compression | deterministic | 4 | 4 | 0 | 0 | 100.00% | 1.000 |
| extraction_quality | model-eval | 7 | 6 | 1 | 0 | 85.71% | 0.801 |
| intent_recognition | model-eval | 5 | 5 | 0 | 0 | 100.00% | 1.000 |
| memory_retrieval | model-eval | 3 | 3 | 0 | 0 | 100.00% | 1.000 |
| memory_update | model-eval | 1 | 1 | 0 | 0 | 100.00% | 1.000 |
| memory_write | model-eval | 4 | 4 | 0 | 0 | 100.00% | 1.000 |

## Limitations

- This evidence contains aggregate metrics only.
- Deterministic or smoke results do not represent live-model latency or quality.
- Category run modes must be used to distinguish deterministic and model-backed evidence.
