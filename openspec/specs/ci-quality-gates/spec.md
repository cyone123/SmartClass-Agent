# ci-quality-gates Specification

## Purpose
TBD - created by archiving change repair-measurement-system. Update Purpose after archive.
## Requirements
### Requirement: CI runs deterministic backend quality checks
The root GitHub Actions workflow SHALL install declared development dependencies and run backend lint, default unit tests, and evaluation-harness unit tests without requiring model API credentials.

#### Scenario: Backend test fails
- **WHEN** Ruff, a backend unit test, or an evaluation-harness unit test fails
- **THEN** the corresponding CI job fails and blocks the workflow

### Requirement: CI validates the evaluation suite
CI SHALL run strict static validation for all evaluation YAML files and SHALL fail on missing files, parse errors, duplicate IDs, unsupported assertions, invalid fields, or an unexpected case count.

#### Scenario: Case is silently skipped by the runner
- **WHEN** a YAML file cannot be loaded or references an unsupported assertion
- **THEN** the validation job fails instead of reducing the reported total case count

### Requirement: CI tests regression-gate behavior
CI SHALL execute deterministic regression fixtures covering a passing baseline, threshold regression, missing category and runtime error.

#### Scenario: Missing category fixture
- **WHEN** the smoke report omits a required category
- **THEN** the regression command exits non-zero

#### Scenario: Valid fixture
- **WHEN** all required categories are present, contain no errors and meet their thresholds
- **THEN** the regression command exits zero

### Requirement: CI builds the frontend and deployment smoke target
CI SHALL run the frontend production build and retain the existing Compose configuration and backend image build checks.

#### Scenario: Frontend build fails
- **WHEN** `npm run build` exits non-zero
- **THEN** the frontend CI job fails

### Requirement: Live-model evaluation remains separately triggered
CI SHALL NOT require live-model evaluation on every push; a separately triggered workflow MAY use configured secrets and SHALL label its reports as `model-eval`.

#### Scenario: Normal push without model secrets
- **WHEN** the root repository receives a normal push
- **THEN** all mandatory deterministic quality gates can complete without model API credentials

