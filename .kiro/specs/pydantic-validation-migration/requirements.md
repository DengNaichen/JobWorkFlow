# Requirements Document

## Introduction

This specification defines a structured migration from the current function-based validation layer (currently centralized in `mcp-server-python/utils/validation.py`) to Pydantic v2 models and validators.

The migration targets consistency, schema clarity, and reduced drift across MCP tool contracts while preserving existing behavior for successful and failing requests.

## Glossary

- **Validation_Layer**: Input parsing and constraint enforcement before business logic execution
- **Pydantic_Request_Model**: A Pydantic v2 model used to validate MCP tool input payloads
- **Pydantic_Response_Model**: A Pydantic v2 model used to shape tool output payloads
- **Behavior_Parity**: Compatibility objective where pre- and post-migration semantics match unless explicitly changed
- **Spec_Alignment**: Verification that implementation behavior remains aligned with existing `.kiro/specs/*/requirements.md` contracts

## Requirements

### Requirement 1: Validation Architecture Migration

**User Story:** As a maintainer, I want validation logic represented as typed Pydantic models, so that tool contracts are explicit, centralized, and less error-prone.

#### Acceptance Criteria

1. THE system SHALL define Pydantic request models for each MCP tool currently validated by helper functions
2. THE system SHALL define Pydantic response models for structured success responses returned by MCP tools
3. THE system SHALL keep existing validation helpers available behind a compatibility layer during migration phases
4. THE system SHALL support phased migration where tools can be switched one-by-one without requiring a single big-bang cutover
5. THE system SHALL enforce strict handling of unknown fields where current specs require `additionalProperties=false`

### Requirement 2: Behavior Parity for Existing MCP Tools

**User Story:** As an operator, I want tool behavior unchanged after migration, so that automation workflows and prompts do not break.

#### Acceptance Criteria

1. WHEN a previously valid request is submitted, THE migrated tool SHALL continue to accept it and produce equivalent business results
2. WHEN an invalid request is submitted, THE migrated tool SHALL preserve existing top-level error shape and error code semantics
3. WHEN per-item business validation currently returns structured item failures (instead of top-level errors), THE migrated tool SHALL preserve that pattern
4. THE migration SHALL preserve existing defaults, required/optional fields, and range constraints for all migrated tools
5. THE migration SHALL preserve case sensitivity and whitespace semantics where existing validators enforce them

### Requirement 3: Error Surface Compatibility

**User Story:** As an MCP client developer, I want stable error responses, so that client-side handling logic remains correct.

#### Acceptance Criteria

1. THE system SHALL continue using `models.errors.ToolError` and existing error codes (`VALIDATION_ERROR`, `DB_NOT_FOUND`, `DB_ERROR`, `INTERNAL_ERROR`, etc.) as the externally visible contract
2. WHEN Pydantic validation fails, THE system SHALL map failures to existing `ToolError` structures and sanitized messages
3. THE system SHALL avoid leaking raw Pydantic internals in user-facing error messages
4. THE system SHALL preserve `retryable` semantics for mapped errors
5. THE system SHALL document any intentional error message wording changes and justify them as non-breaking

### Requirement 4: Spec Alignment Across Existing Features

**User Story:** As a project owner, I want this migration aligned with all current feature specs, so that one refactor does not silently violate prior contracts.

#### Acceptance Criteria

1. THE migration SHALL produce an explicit alignment matrix referencing these spec scopes:
   - `.kiro/specs/bulk-read-new-jobs`
   - `.kiro/specs/bulk-update-job-status`
   - `.kiro/specs/scrape-jobs-mcp`
   - `.kiro/specs/initialize-shortlist-trackers`
   - `.kiro/specs/career-tailor`
   - `.kiro/specs/update-tracker-status`
   - `.kiro/specs/finalize-resume-batch`
2. FOR each scope above, THE matrix SHALL record impacted request fields, changed validator location, and parity verification status
3. THE migration SHALL identify and document any spec ambiguities or conflicts discovered during model normalization
4. WHEN a conflict is found between runtime behavior and written requirements, THE migration SHALL log a decision record before release
5. THE migration SHALL be considered complete only when all rows in the alignment matrix are either `Parity Confirmed` or `Intentional Change Approved`

### Requirement 5: Phased Delivery and Rollback Safety

**User Story:** As a release engineer, I want controlled rollout and rollback, so that migration risks are minimized.

#### Acceptance Criteria

1. THE implementation SHALL define migration phases with clear entry and exit criteria
2. THE implementation SHALL support tool-level fallback to legacy validators during rollout
3. THE implementation SHALL include a documented rollback path that can be executed without database migration
4. EACH phase SHALL include required automated tests and pass criteria
5. THE final phase SHALL remove duplicated legacy validation code only after parity is validated

### Requirement 6: Test Strategy for Migration Confidence

**User Story:** As an engineer, I want clear test gates, so that validation migration can be merged safely.

#### Acceptance Criteria

1. THE migration SHALL add focused unit tests for new Pydantic models and validators
2. THE migration SHALL retain or adapt existing tool integration tests to assert compatibility
3. THE migration SHALL include golden-path and failure-path tests for each migrated tool payload model
4. THE migration SHALL include regression coverage for edge cases currently captured in `mcp-server-python/tests/test_validation.py`
5. THE migration SHALL define a completion gate requiring all migrated-tool tests to pass in CI

### Requirement 7: Contract Documentation Update

**User Story:** As a team member, I want updated docs reflecting the new validation architecture, so onboarding and maintenance remain efficient.

#### Acceptance Criteria

1. THE system SHALL document the new validation architecture in `mcp-server-python/README.md` and/or architecture docs
2. THE system SHALL document model locations and naming conventions for request/response schemas
3. THE system SHALL document conversion rules between Pydantic errors and `ToolError`
4. THE system SHALL document migration status per tool (legacy vs migrated)
5. THE system SHALL provide at least one example payload per migrated tool using the new model contract terminology
