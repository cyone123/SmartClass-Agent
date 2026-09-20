## ADDED Requirements

### Requirement: Compression preserves protocol-valid retained history
The system SHALL compress only completed conversation segments and preserve the original content blocks, continuation metadata and complete tool call/result associations in retained raw turns.

#### Scenario: Retained turn contains provider metadata
- **WHEN** compression retains recent turns containing tool calls and provider-required signatures or reasoning metadata
- **THEN** those turns MUST remain valid for the next same-provider invocation without loss or reconstruction of opaque metadata

#### Scenario: Boundary splits a tool exchange
- **WHEN** the proposed compression boundary would separate a tool call from its result or include unfinished exchanges
- **THEN** the system MUST choose a complete safe boundary or skip compression without destructively changing state

### Requirement: Compression uses fixed model configuration and safe summary input
The system SHALL use the compression role from the current run or workflow snapshot and MUST exclude provider-private reasoning and signatures from the text summarized by a different model.

#### Scenario: Global compression role changed
- **WHEN** compression executes for a workflow created under an older configuration
- **THEN** it MUST use that workflow's compression role snapshot rather than the current global role

#### Scenario: Compression initialization or invocation fails
- **WHEN** the configured compression model cannot initialize, consume the prepared input or produce a usable summary
- **THEN** the system MUST preserve original history, report compression failure through existing progress semantics and allow the chat run to finish as before
