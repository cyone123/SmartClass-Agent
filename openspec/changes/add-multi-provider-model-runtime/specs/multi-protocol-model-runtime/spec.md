## Purpose

Provide equivalent SmartClass model execution across supported chat protocols while preserving teaching approvals, complete tool exchanges, internal message metadata, safe streaming output, and independent background model tasks.

## ADDED Requirements

### Requirement: Supported protocols serve configured business roles
The system SHALL support OpenAI Chat Completions, Anthropic Messages and Gemini Developer API generateContent for roles whose required capabilities are supported, including the existing video frame analysis role when image input is supported.

#### Scenario: Anthropic or Gemini serves the main role
- **WHEN** a valid main-role configuration selects either native protocol
- **THEN** the system MUST support conversation streaming and the existing teaching action tool protocol without bypassing teaching confirmations

#### Scenario: Vision role uses a different provider
- **WHEN** video frame analysis selects an image-capable model on another connection
- **THEN** the system MUST send the existing text and frame inputs through that connection independently of the main role

### Requirement: Tool and structured output contracts are preserved
The system SHALL preserve tool names, argument validation semantics, call identifiers and result associations, and SHALL explicitly select and validate the structured-output strategy required by a task.

#### Scenario: Model makes multiple tool calls
- **WHEN** a supported model emits parallel or sequential tool calls
- **THEN** each result MUST be associated with the correct call and the next request MUST contain a complete valid exchange without duplicate execution

#### Scenario: Required structured output is invalid
- **WHEN** output fails the business schema or the model does not support the required strategy
- **THEN** the task MUST report a validation/capability failure or use an explicitly configured safe fallback, never treat unrestricted text as validated output

### Requirement: Provider continuation metadata survives internal history
The system SHALL preserve provider-required reasoning metadata and signatures through stream assembly, internal persistence and subsequent same-provider requests, without rendering those fields as ordinary user text.

#### Scenario: Tool continuation requires metadata
- **WHEN** a DeepSeek reasoning-enabled exchange or Gemini/Anthropic continuation requires provider-specific metadata
- **THEN** the next request MUST include the required metadata in its supported representation after checkpoint serialization and restoration

#### Scenario: Final stream chunk has no display text
- **WHEN** a chunk contains only usage or continuation metadata
- **THEN** the system MUST retain that information without emitting a spurious text token

### Requirement: Display output and runtime history have separate representations
The system SHALL extract only displayable text for chat history and ordinary SSE tokens while retaining complete internal messages needed for execution.

#### Scenario: Response contains text and non-text blocks
- **WHEN** a model response contains text, reasoning, signatures or tool metadata
- **THEN** the ordinary chat output MUST include only the displayable text and MUST NOT stringify the entire response object

#### Scenario: Existing client consumes a different provider
- **WHEN** a run uses any supported protocol
- **THEN** the client MUST continue consuming the existing SSE event types and their meanings without provider-specific event handlers

### Requirement: History conversion preserves safe continuation boundaries
The system SHALL preserve system instruction precedence and complete tool exchanges when preparing protocol-specific history, and MUST reject unsupported continuation conversions.

#### Scenario: Provider changes between completed turns
- **WHEN** a new run selects another protocol after all prior tool exchanges are complete
- **THEN** the system MUST prepare compatible completed history without forging signatures, promoting untrusted memory to instructions or sending private metadata as ordinary text

#### Scenario: Tool exchange is incomplete
- **WHEN** an attempted protocol switch would cross an unfinished tool exchange
- **THEN** the system MUST refuse the switch instead of replaying an invalid partial exchange

### Requirement: Retry and fallback have a bounded execution policy
The system SHALL classify model errors, enforce one overall retry/deadline budget per logical request, honor cancellation, and distinguish role inheritance from explicit runtime fallback.

#### Scenario: Transient request failure occurs before commitment
- **WHEN** a retryable transport, rate-limit or server error occurs before text is committed or tools are executed
- **THEN** retries and any configured fallback MUST respect the total budget and preserve the task's fixed configuration and memory context

#### Scenario: Output or tool effects already exist
- **WHEN** a failure occurs after user-visible text is committed or a tool has executed
- **THEN** the system MUST NOT automatically restart the whole Agent on another model or duplicate previously committed output or effects

#### Scenario: Authentication or explicit capability fails
- **WHEN** authentication, permissions or a required configured capability is invalid
- **THEN** the system MUST fail with a sanitized classification rather than silently selecting another account or relaxing the requirement

### Requirement: Background and concurrent calls use their assigned configuration
The system SHALL isolate concurrent configuration, tools and credentials, and SHALL execute memory reflection with the model configuration captured when its job was enqueued.

#### Scenario: Two runs use different connections
- **WHEN** concurrent runs bind different tools or credentials
- **THEN** neither run MUST mutate or inherit the other run's model binding or credentials

#### Scenario: Reflection executes after configuration changes
- **WHEN** a queued reflection job starts after a backend restart with new global role settings
- **THEN** it MUST use its persisted enqueue-time model configuration and current referenced credentials, or fail explicitly if those credentials are unavailable

#### Scenario: Legacy reflection job has no model snapshot
- **WHEN** an existing queued job is first processed by the new runtime
- **THEN** it MUST persist a one-time current configuration adoption before model invocation and identify that adoption as legacy in safe metadata

### Requirement: Usage and errors are normalized without sensitive telemetry
The system SHALL report available token usage and provider-independent error categories without inventing zero usage or logging model input, output, reasoning or credentials.

#### Scenario: Provider omits usage
- **WHEN** no usage metadata is available
- **THEN** the system MUST mark usage as unavailable rather than a measured zero

#### Scenario: Provider returns an error with sensitive data
- **WHEN** a provider error includes request or authentication details
- **THEN** observations and client errors MUST retain an actionable category while excluding those details
