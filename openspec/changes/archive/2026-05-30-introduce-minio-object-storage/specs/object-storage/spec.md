## ADDED Requirements

### Requirement: Configurable storage backend

The system SHALL provide a configurable storage backend for SmartClass attachment files and artifact files.

#### Scenario: Local storage remains the default

- **WHEN** no object storage backend is enabled in configuration
- **THEN** attachment and artifact file behavior MUST continue to use the existing local storage semantics

#### Scenario: MinIO backend is selected

- **WHEN** configuration selects the MinIO backend and all required MinIO settings are present
- **THEN** new attachment files and artifact files MUST be stored through the MinIO-compatible storage backend

#### Scenario: MinIO configuration is incomplete

- **WHEN** configuration selects the MinIO backend but endpoint, bucket, access key, secret key, or required client settings are missing
- **THEN** backend startup or storage service initialization MUST fail with a clear configuration error

### Requirement: Stable stored object contract

The system SHALL represent stored files with stable object metadata instead of requiring business code to interpret host filesystem paths.

#### Scenario: File is stored

- **WHEN** an attachment or artifact file is written to storage
- **THEN** the system MUST persist a stable storage key, filename, MIME type, size, and SHA-256 when available

#### Scenario: Existing local records are read

- **WHEN** an existing record only has a legacy local `storage_path`
- **THEN** the storage service MUST still be able to read, download, preview, and delete the file through the local compatibility backend

#### Scenario: URL is requested

- **WHEN** the API needs a download URL or preview URL for a ready artifact
- **THEN** URL generation MUST be centralized in the storage/API layer and MUST NOT require the frontend to know MinIO bucket names or object keys

### Requirement: Attachment upload through object storage

The system SHALL store conversation attachments through the configured storage service.

#### Scenario: Document attachment upload succeeds

- **WHEN** a user uploads a supported document attachment for a plan and thread
- **THEN** the attachment content MUST be written to the configured storage backend and the response MUST include the existing attachment metadata contract

#### Scenario: Voice attachment upload succeeds

- **WHEN** a user uploads a supported voice attachment for transcription
- **THEN** the voice content MUST be stored through the configured storage backend before transcription begins

#### Scenario: Attachment analysis needs a local path

- **WHEN** an attachment analysis, speech, video, or skill component requires a filesystem path
- **THEN** the storage service MUST provide a managed temporary local file and clean it up after the operation completes

### Requirement: Artifact collection through object storage

The system SHALL collect Agent-generated artifact outputs into the configured storage backend while preserving the unified artifact contract.

#### Scenario: Artifact generation starts

- **WHEN** an artifact record is created in running status
- **THEN** the system MUST assign deterministic storage metadata without exposing a ready download URL

#### Scenario: Artifact output is marked ready

- **WHEN** the Agent workspace produces a valid PPT, DOCX, or HTML output file
- **THEN** the artifact service MUST upload the file to the configured storage backend, update size/MIME/status metadata, maintain revision relationships, and emit a ready artifact payload compatible with the existing frontend contract

#### Scenario: Artifact output upload fails

- **WHEN** storing a generated artifact fails
- **THEN** the artifact MUST be marked failed with a user-readable error summary and enough structured log context to diagnose the storage failure

### Requirement: Download and preview storage compatibility

The system SHALL serve downloads and previews for locally stored and MinIO-stored files through existing API routes.

#### Scenario: Artifact download requested

- **WHEN** a ready artifact download URL is opened
- **THEN** the backend MUST return the file content with the correct filename and MIME type, either by proxying storage content or by issuing a controlled redirect to a presigned object URL

#### Scenario: HTML artifact preview requested

- **WHEN** a ready `html-game` artifact is previewed
- **THEN** the backend MUST read the HTML from storage and render it through the existing sandboxed iframe preview flow

#### Scenario: Missing stored content

- **WHEN** a database record exists but the object is missing from storage
- **THEN** the API MUST return a clear not-found error without exposing internal bucket paths or host filesystem paths

### Requirement: OnlyOffice object storage integration

The system SHALL support OnlyOffice preview and save callbacks for artifact files stored in MinIO.

#### Scenario: Office preview config requested

- **WHEN** a DOCX, PPTX, or PDF artifact is ready and preview config is requested
- **THEN** the generated document URL MUST allow OnlyOffice to fetch the file through a backend public URL or a bounded presigned URL

#### Scenario: OnlyOffice saves artifact edits

- **WHEN** OnlyOffice sends a save callback for an artifact file
- **THEN** the backend MUST download the edited document and write it back through the configured storage service while preserving artifact status and revision metadata

#### Scenario: OnlyOffice saves knowledge file edits

- **WHEN** OnlyOffice sends a save callback for a knowledge file that remains on local storage
- **THEN** the existing knowledge-file save and re-ingestion behavior MUST remain compatible

### Requirement: Storage observability and safety

The system SHALL log storage operations with correlation metadata while avoiding sensitive content leakage.

#### Scenario: Storage operation is attempted

- **WHEN** upload, download, delete, preview read, or callback write is attempted
- **THEN** logs MUST include backend type, storage key or legacy local marker, plan id, thread id when available, artifact id or attachment id when available, status, duration, and error category when failed

#### Scenario: Secret configuration exists

- **WHEN** MinIO credentials or presigned URLs are configured or generated
- **THEN** logs, SSE events, API error messages, and artifact trace entries MUST NOT include full secret values or long-lived signed URLs

#### Scenario: Object key is built

- **WHEN** the system creates a storage key for an attachment or artifact
- **THEN** the key MUST be scoped by file kind and plan/thread/run identifiers and MUST reject path traversal or untrusted absolute path content
