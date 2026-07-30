## ADDED Requirements

### Requirement: Strict evaluation case discovery
The evaluation harness SHALL recursively discover every YAML case, validate it, reject duplicate case identifiers, and filter categories using the case `category` field rather than the directory name.

#### Scenario: Current suite is discovered
- **WHEN** suite validation runs against the current `backend/tests/evals/cases` tree
- **THEN** all 24 YAML files are either loaded successfully or reported as explicit validation errors, with no warning-only omissions

#### Scenario: Category filter uses metadata
- **WHEN** a user requests category `memory_retrieval`
- **THEN** the runner returns cases whose YAML `category` equals `memory_retrieval` regardless of their parent directory name

### Requirement: Assertion declarations and handlers remain consistent
Every assertion type accepted by `EvalAssertion` SHALL have a registered execution handler and deterministic unit tests, or the case SHALL fail validation before runtime.

#### Scenario: Unsupported assertion is rejected
- **WHEN** a case contains an assertion type without a registered handler
- **THEN** suite validation fails with the case ID and unsupported assertion type

#### Scenario: Judge failure is not converted to a passing score
- **WHEN** an LLM Judge call fails or returns an invalid score
- **THEN** the assertion and case are reported as `ERROR` rather than using a fallback score

### Requirement: Evaluator output contracts are stable
Each evaluator SHALL expose a documented `actual_output` contract, and case assertions SHALL reference only fields provided by that contract.

#### Scenario: Invalid field reference is detected
- **WHEN** suite validation finds an assertion field that is not part of its category evaluator contract
- **THEN** validation fails before any model or graph execution begins

### Requirement: Report statistics use explicit semantics
Evaluation reports SHALL expose pass rate, error rate, average score, and per-category metrics as separate fields with stable formulas.

#### Scenario: Category metrics are generated
- **WHEN** a suite contains passed, failed, and error results
- **THEN** each category reports its case count, passed, failed, error, pass rate, error rate, and average score

#### Scenario: Errors fail regression
- **WHEN** any required category contains an `ERROR` result
- **THEN** the regression check exits non-zero even if the average score exceeds its threshold

#### Scenario: Missing category fails regression
- **WHEN** a required category is absent from the report
- **THEN** the regression check exits non-zero and identifies the missing category

### Requirement: Reports include reproducibility metadata
Every non-legacy evaluation report SHALL record its schema version, run mode, dataset fingerprint, Git commit, environment summary, and non-sensitive model configuration.

#### Scenario: Deterministic report has no model
- **WHEN** a deterministic suite uses only fake or local deterministic components
- **THEN** the report marks `run_mode` as `deterministic` and records an empty model configuration without pretending to represent live-model performance

#### Scenario: Live-model report identifies the model
- **WHEN** a suite invokes a real model
- **THEN** the report records provider, model name and relevant decoding parameters without recording API credentials
