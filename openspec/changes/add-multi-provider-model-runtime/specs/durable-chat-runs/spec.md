## ADDED Requirements

### Requirement: Runs persist resolved model configuration before execution
The system SHALL persist an immutable, versioned model configuration snapshot before the first model invocation of each run, containing enough non-secret information to execute after restart without resolving changed global role settings.

#### Scenario: New run is queued
- **WHEN** a new run is accepted
- **THEN** its effective model configuration MUST be persisted before execution and MUST NOT accept a caller-supplied internal snapshot

#### Scenario: Persisted configuration is restored
- **WHEN** execution loads a run snapshot after restart
- **THEN** model identity, protocol, endpoint, role bindings and parameter policy MUST come from the snapshot while secret values are resolved from its credential references

### Requirement: Teaching workflows retain configuration across approval runs
The system SHALL keep the same model configuration from teaching-workflow initiation through clarification, approval pauses and artifact completion or cancellation, including parallel artifact generation.

#### Scenario: Approval is resumed under changed global configuration
- **WHEN** approval creates a new run for an existing teaching workflow after global configuration changed
- **THEN** the new run MUST inherit the workflow's prior model snapshot and preserve all existing approval validation

#### Scenario: New workflow begins
- **WHEN** a completed or cancelled workflow is followed by a new teaching task or artifact revision, or the user explicitly restarts the teaching task
- **THEN** the new workflow MUST capture the currently loaded configuration rather than remain indefinitely pinned to the previous workflow

#### Scenario: Parallel artifacts are generated
- **WHEN** a workflow fans out into PPTX, DOCX and HTML generation
- **THEN** every branch MUST use the same workflow configuration snapshot for its assigned roles

#### Scenario: New workflow intent is recognized during execution
- **WHEN** model-based routing recognizes an explicit restart or new workflow within a run that entered with an existing workflow
- **THEN** the new workflow MUST use the current configuration captured at run acceptance, preserve the immutable prior snapshot, and record the configuration selection without switching within an unfinished tool exchange

### Requirement: Legacy runs adopt configuration once
The system SHALL support existing run records and checkpoints without model snapshots by capturing and persisting the currently valid configuration once before their next model invocation.

#### Scenario: Legacy approval checkpoint resumes
- **WHEN** an existing pending approval has no model snapshot
- **THEN** the system MUST adopt the current valid configuration once, mark the adoption as legacy in safe metadata and use that snapshot for subsequent continuation

#### Scenario: Legacy adoption fails
- **WHEN** current configuration cannot be validated or its adoption cannot be persisted
- **THEN** execution MUST fail before contacting a model and MUST NOT claim that an original historical model configuration was recovered
