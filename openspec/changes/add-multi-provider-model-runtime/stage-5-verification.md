# Stage 5 verification — business regression, evidence, and release

Date: 2026-09-22 (Asia/Shanghai)

## Outcome

Stage 5 tasks 5.1–5.8 are complete. The overall OpenSpec change remains **incomplete** because native
Anthropic/Gemini live gate 3.11 and OpenRouter/DeepSeek/Zhipu live gate 4.6 remain unchecked. This stage does
not reinterpret deterministic fixtures as provider support or model quality.

Machine-readable acceptance summary: `stage-5-acceptance.json`.

## Evidence metadata and privacy

Eval and live benchmark model summaries now come from the resolved runtime snapshot plus allowlisted invocation
metadata. Each invoked role records provider, protocol, model, thinking/reasoning and structured strategy,
configuration/capability rules version, integration versions, fallback identities, provider routing, and
actual upstream or `unknown`. The harness no longer infers provider from endpoint host or model slug.

Schema 2.0 remains backward compatible: legacy flat model summaries are accepted, while new per-role metadata is
an additive object. Baseline promotion re-sanitizes it. Tests prove endpoint, credential reference, key, header,
prompt, completion, object key, host path, and provider-private reasoning cannot enter promoted summaries.
Thinking and routing changes remain distinguishable and cannot be merged as equivalent configuration evidence.

## Business regression

Deterministic cross-layer command (from `backend/`):

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
.\.venv\Scripts\python.exe -m pytest -p pytest_asyncio.plugin `
  tests/test_stage5_business_regression.py `
  tests/test_main_graph_orchestration.py tests/test_approval_flow.py `
  tests/test_model_workflows.py tests/test_memory_reflection_worker.py `
  tests/test_context_compression.py tests/test_artifact_flow.py `
  tests/test_storage_service.py tests/test_workspace_manager.py `
  tests/test_skill_aware_agent.py -q
```

Result: **118 passed, 0 failed, 0 ERROR**, pass rate 100%. `avg_score` is not applicable because these are pytest
contracts, not scored model evaluations. Coverage includes normal chat, metadata/plan approval and restart,
three-artifact fan-out, artifact revision, enqueue-time memory reflection snapshot, compression continuation,
explicit role selection, WorkspaceToolset authorization, and StorageService persistence/materialization.

## Repository gates

| Gate | Result |
|---|---|
| Default backend pytest | 439 passed, 18 deselected, 0 failed, 0 ERROR (66.63 s) |
| `ruff check app tests` | passed |
| `ruff format --check app tests` | 167 files formatted, passed |
| Eval suite strict validation | 24 YAML files / 24 cases, passed |
| OpenSpec strict validation | passed |

The 18 deselected tests retain explicit `model_eval`/`integration` separation. Default pytest is deterministic
or offline-contract evidence, not live protocol verification.

## Deployment and rollback evidence

- Root env examples expose `MODEL_CONFIG_PATH`; `model-config.example.yaml` documents env-only credentials and
  capability verification state.
- Compose mounts the model YAML at `/app/config/model-config.yaml` read-only. An offline test loads the same file
  through a Windows repository-relative path and checks the container path/mount contract.
- `InMemoryConfigRepository` proves Graph/Agent role callers depend only on `ConfigRepository.load()`, leaving
  Database/Secret/control-plane implementation for a future change. The public DTO example intentionally omits
  endpoint and credential references.
- Release instructions rehearse additive old-record adoption, workflow snapshot pinning, credential removal
  failure, and rollback preflight. A snapshot requiring `anthropic_messages` is rejected when the supported
  protocol set represents an old OpenAI-only runtime; pending new-protocol checkpoints must be completed or
  cancelled before program downgrade.

See `docs/model-provider-runtime.md` and `docs/deployment/model-runtime-release.md`.

## Live and baseline status

The provider smoke report remains **0 passed, 0 failed, 13 unverified**. No unverified check is counted in a pass
rate, and no `avg_score` exists for protocol smoke. No new live schema-2.0 business report was generated, so
baseline promotion was not attempted. `FAILED` and `ERROR` remain separate fields; neither is replaced by
`avg_score`. The existing fail-closed promotion rule is unchanged.
