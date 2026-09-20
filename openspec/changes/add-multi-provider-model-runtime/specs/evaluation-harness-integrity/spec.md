## ADDED Requirements

### Requirement: Model evidence identifies actual resolved role configuration
The evaluation and benchmark system SHALL record the actual provider, protocol, model, relevant decoding/thinking strategy, configuration version and integration version for each real model role invoked, including fallback attempts, using a non-sensitive allowlist.

#### Scenario: Roles use different providers
- **WHEN** a real evaluation uses different main, structured or memory providers
- **THEN** the report MUST identify their actual resolved configurations rather than infer one provider from a global URL or model name

#### Scenario: Aggregator chooses an upstream
- **WHEN** an aggregator exposes the actual upstream identity
- **THEN** evidence MUST distinguish the configured aggregator from the actual upstream; if unavailable it MUST record upstream identity as unknown rather than infer it

#### Scenario: Sensitive configuration exists
- **WHEN** report metadata is generated
- **THEN** it MUST exclude keys, credential references, endpoint URLs, host paths, request headers, prompts, completions and provider-private reasoning metadata

### Requirement: Compatibility evidence distinguishes offline and live verification
The system SHALL distinguish offline protocol contracts, live-provider smoke verification and business-effect evaluations, and MUST NOT treat skipped or unavailable checks as successful provider support evidence.

#### Scenario: Live credentials are missing
- **WHEN** a requested real-provider smoke cannot run because credentials or access are unavailable
- **THEN** its evidence MUST report unverified or skipped status with a safe reason and MUST NOT count it as a pass

#### Scenario: Default tests are executed
- **WHEN** the default offline test suite runs
- **THEN** protocol checks MUST use deterministic fixtures without external requests and MUST NOT present their outcomes as live-model quality

#### Scenario: Baseline evidence is prepared
- **WHEN** new model-configuration metadata is included in baseline evidence
- **THEN** the report MUST retain existing schema compatibility, fail-closed regression gates and promotion allowlists, and configurations with different effective thinking or routing policies MUST NOT be merged as equivalent runs
