## Purpose

Define stable, versioned model provider configuration so SmartClass can select independent model connections for teaching roles, preserve credential boundaries, and later support a management interface without changing runtime behavior.

## ADDED Requirements

### Requirement: Protocol and provider configuration are independent
The system SHALL separately identify protocol, provider preset, connection, model configuration and business role, and SHALL support multiple connections for one preset.

#### Scenario: Aggregator serves another vendor model
- **WHEN** an OpenRouter connection using openai_chat selects an anthropic-prefixed model ID
- **THEN** the system MUST use that connection's explicitly selected protocol and credentials without inferring Anthropic Messages from the model ID

#### Scenario: Multiple accounts use one provider
- **WHEN** two connections share a preset but have different credential references
- **THEN** role selection MUST resolve the selected connection without mixing credentials or configuration with the other connection

### Requirement: Backend configuration has deterministic precedence
The system SHALL load versioned backend file configuration and environment credential references at startup, with explicit role file configuration taking precedence over legacy role configuration.

#### Scenario: Explicit file configuration is incomplete
- **WHEN** a role is explicitly configured in the file but its required connection identity cannot be resolved
- **THEN** configuration validation MUST report the invalid role without filling its credentials or endpoint from legacy role variables

#### Scenario: Deployment has not migrated
- **WHEN** only complete and valid legacy model environment settings are supplied
- **THEN** the system MUST resolve equivalent model connections and preserve documented role behavior

#### Scenario: File changes after startup
- **WHEN** an operator changes the configuration file while the backend is running
- **THEN** the running process MUST continue using its loaded configuration and deployment instructions MUST require restart for the new configuration to apply

### Requirement: Role inheritance preserves connection identity
The system SHALL inherit a complete model configuration only when the role's identity configuration is absent or explicit inheritance is selected, and MUST reject inheritance cycles and ambiguous partial identities.

#### Scenario: Memory inherits a configured role
- **WHEN** memory has no dedicated identity and the first eligible role in its documented inheritance chain is configured
- **THEN** memory MUST inherit that role's model, protocol, endpoint and credential references together

#### Scenario: Dedicated identity is partially configured
- **WHEN** a dedicated role provides a model ID but requires credentials or an endpoint from another role to become usable
- **THEN** validation MUST fail with a field-level migration diagnostic instead of constructing a mixed connection

#### Scenario: Optional capability is disabled
- **WHEN** an optional feature is disabled and its dedicated credentials are absent
- **THEN** the backend MUST NOT require those credentials to serve unrelated enabled features

### Requirement: Presets describe supported connection and parameter options
The system SHALL provide OpenAI, Anthropic, Google Gemini, OpenRouter, DeepSeek, Zhipu and custom connection presets with supported protocol choices, credential fields and parameter rules.

#### Scenario: Operator uses a custom endpoint and model
- **WHEN** a custom connection supplies an explicit supported protocol, valid endpoint, credentials and model capability declaration
- **THEN** the system MUST allow its use without requiring the model ID to appear in a built-in catalog

#### Scenario: Explicit parameter is incompatible
- **WHEN** an explicit parameter or protocol choice is unsupported by the selected connection and model mode
- **THEN** the system MUST reject it with a safe actionable error rather than silently dropping the parameter or switching protocols

### Requirement: Required capabilities are validated by effective configuration
The system SHALL distinguish supported, unsupported and unknown capabilities for the effective connection, model, parameter mode and adapter version, and SHALL validate the capabilities required by each role before invocation.

#### Scenario: Main role cannot perform tool calls
- **WHEN** a selected main-role model has unsupported or undeclared required tool capabilities
- **THEN** the system MUST reject that use before submitting the business request and identify the missing capability

#### Scenario: Custom model capability is declared
- **WHEN** an operator declares a capability for a custom model
- **THEN** the system MUST distinguish the declaration from verified support and MUST NOT allow it to override a known protocol or adapter limitation

### Requirement: Configuration versions and credential references remain separate
The system SHALL version non-secret configuration independently of credentials, resolve secrets only at the invocation boundary, and exclude secrets from persisted configuration snapshots and public configuration representations.

#### Scenario: Credential is rotated
- **WHEN** a credential reference resolves to a replacement secret
- **THEN** subsequent invocations MUST use that reference's current secret without changing the fixed model identity or exposing the secret in snapshots, diagnostics or telemetry

#### Scenario: Credential is unavailable
- **WHEN** a fixed connection's credential reference cannot be resolved
- **THEN** invocation MUST fail explicitly without borrowing credentials from another account

#### Scenario: Configuration is presented outside internal runtime storage
- **WHEN** the system creates a public configuration representation or an observation
- **THEN** it MUST omit secrets, sensitive headers, credential references and internal endpoint details while retaining safe stable identifiers
