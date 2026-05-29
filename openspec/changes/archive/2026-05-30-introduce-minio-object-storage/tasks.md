## 1. Configuration And Storage Abstraction

- [x] 1.1 Add the MinIO/S3-compatible Python dependency to the backend dependency manifest used by the project.
- [x] 1.2 Add backend configuration fields for storage backend selection, MinIO endpoint, bucket, credentials, region, secure/path-style behavior, presigned URL TTL, and proxy-vs-presigned download mode.
- [x] 1.3 Validate MinIO configuration during storage service initialization when the MinIO backend is selected, while keeping local storage as the default.
- [x] 1.4 Create a storage service module with local and MinIO backend implementations for writing bytes/files, reading streams/text, deleting objects, checking existence, generating object keys, and materializing managed temporary local files.
- [x] 1.5 Add structured storage error categories and log helpers that include backend type, object key, plan id, thread id, artifact id or attachment id, duration, status, and failure category without logging secrets.

## 2. Data Model And Compatibility

- [x] 2.1 Add additive database fields for `storage_backend` and `storage_key` to `AttachmentFile` and `ArtifactFile`, with startup compatibility patches or migrations matching current project conventions.
- [x] 2.2 Update schemas and serializers to keep existing API response compatibility while avoiding new frontend dependency on storage keys or bucket details.
- [x] 2.3 Implement legacy fallback so records with only local `storage_path` continue to download, preview, delete, and participate in OnlyOffice flows.
- [x] 2.4 Add deterministic object key builders for attachments and artifacts scoped by file kind, plan id, thread id, artifact type, run id, and sanitized filenames.

## 3. Attachment Upload And Analysis Flow

- [x] 3.1 Update document attachment upload to store content through the storage service and persist storage metadata after validation and duplicate checks.
- [x] 3.2 Update voice attachment upload/transcription to store through the storage service and provide speech runtime with a managed temporary local file.
- [x] 3.3 Update chat attachment retrieval and analysis to validate stored object existence through the storage service and materialize temporary paths for Agent attachment analysis.
- [x] 3.4 Update video attachment analysis call sites, if any require direct paths, to use the same managed temporary file pattern.
- [x] 3.5 Preserve existing plan/thread ownership checks, allowed extension checks, size limits, SHA-256 duplicate behavior, and user-readable upload errors.

## 4. Artifact Generation, Revision, And Collection Flow

- [x] 4.1 Update running artifact creation to assign storage backend/key metadata without exposing a download URL before the artifact is ready.
- [x] 4.2 Update `mark_artifact_ready` to upload workspace output files through the storage service, update MIME/size/name/status metadata, and maintain current/revision relationships.
- [x] 4.3 Update artifact failure handling so storage upload errors mark the artifact failed and surface a concise user-readable error summary.
- [x] 4.4 Ensure SSE `artifact` payloads and frontend artifact store behavior remain compatible for running, ready, failed, current, and historical revision records.
- [x] 4.5 Verify generated PPT, DOCX, and HTML artifact flows still collect outputs from the Agent workspace before storage upload.

## 5. Download, HTML Preview, And OnlyOffice Flow

- [x] 5.1 Refactor `/file/download/{file_kind}/{file_id}` to serve local and MinIO-backed artifact files through the storage service with correct filename and MIME type.
- [x] 5.2 Refactor HTML artifact content and preview routes to read UTF-8 HTML from the storage service while preserving the existing sandboxed iframe wrapper.
- [x] 5.3 Refactor OnlyOffice config generation so document URLs work for MinIO-backed artifacts using backend public URLs or bounded presigned URLs.
- [x] 5.4 Refactor OnlyOffice save callback so artifact edits are written back through the storage service and knowledge-file local callback behavior remains compatible.
- [x] 5.5 Ensure ready-only download URL exposure, failed artifact error display, and missing-object not-found responses stay consistent with the artifact contract.

## 6. Tests And Verification

- [x] 6.1 Add unit tests for local storage backend compatibility and MinIO backend behavior using a fake or mocked client.
- [x] 6.2 Add tests for missing MinIO configuration, invalid object keys, path traversal rejection, storage upload failure, storage read failure, and delete fallback behavior.
- [x] 6.3 Add API/service tests for attachment upload, voice attachment temporary materialization, chat attachment analysis path materialization, and duplicate attachment behavior.
- [x] 6.4 Add artifact service tests for running creation, ready upload, failed upload, revision current-flag updates, and serialized artifact URLs.
- [x] 6.5 Add API tests for artifact download, HTML content/preview, OnlyOffice config, and OnlyOffice callback write-back across local and MinIO-backed records.
- [x] 6.6 Run the relevant backend test suite and record any skipped live MinIO integration checks.
