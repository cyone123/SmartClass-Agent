## ADDED Requirements

### Requirement: Raw evaluation output is separated from committed evidence
The system SHALL keep raw evaluation outputs in an ignored local directory and SHALL generate committed benchmark evidence only through an explicit sanitization and promotion step.

#### Scenario: Normal evaluation run
- **WHEN** a developer runs the evaluation CLI
- **THEN** the detailed raw report is written under `backend/tests/evals/results` and is not automatically committed as a baseline

#### Scenario: Baseline promotion
- **WHEN** a developer promotes a successful report with a baseline identifier
- **THEN** the system writes a manifest, sanitized summary, and human-readable report under `docs/benchmarks/baselines/<baseline-id>/`

### Requirement: Benchmark evidence is reproducible
Each promoted baseline SHALL contain the commands, code revision, dataset fingerprint, environment, run mode, sample size, metric definitions and limitations required to reproduce and interpret the result.

#### Scenario: Reviewer inspects a baseline
- **WHEN** a reviewer opens a committed benchmark directory
- **THEN** the reviewer can identify what was run, under which conditions, and which raw metrics produced each published number

### Requirement: Committed summaries are privacy-safe
Committed benchmark files MUST NOT include prompts, completions, memory bodies, attachment contents, authorization data, signed URLs, object keys, host paths, or full unbounded error messages.

#### Scenario: Sensitive source report is sanitized
- **WHEN** a raw report contains a bearer token, local path, user content or signed URL
- **THEN** the promoted summary contains only allowlisted aggregate fields and redacted bounded error categories

### Requirement: Baselines are immutable and explicitly versioned
A promoted baseline SHALL use a unique identifier and SHALL NOT be overwritten by a normal evaluation run.

#### Scenario: Duplicate baseline identifier
- **WHEN** promotion targets an existing baseline identifier
- **THEN** the command fails unless an explicit replacement option is provided and the change is recorded
