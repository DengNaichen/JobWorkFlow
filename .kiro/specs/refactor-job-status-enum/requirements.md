# Requirements Document: Refactor Job Status to Enum

## Introduction

This specification defines the requirements for refactoring hardcoded job status strings into type-safe, centralized Enum definitions. The goal is to improve code quality, maintainability, and robustness without altering the application's external behavior.

## Glossary

- **Enum**: An enumeration; a set of symbolic names bound to unique, constant values.
- **Magic String**: A hardcoded string literal used in application logic without a clear explanation or centralized definition.
- **Behavior Parity**: The principle that the application's observable behavior must remain identical before and after the refactoring.
- **Single Source of Truth**: The practice of structuring information models so that every data element is stored exactly once.

## Requirements

### Requirement 1: Centralized and Type-Safe Status Definitions

**User Story:** As a developer, I want job statuses defined as Enums in a central location, so that I have a single source of truth and can avoid magic strings.

#### Acceptance Criteria

1.  THE system SHALL define a `JobDbStatus` Enum containing all valid statuses for the database.
2.  THE system SHALL define a `JobTrackerStatus` Enum containing all valid statuses for Markdown tracker files.
3.  THESE Enums SHALL be located in a single new file at `mcp-server-python/models/status.py`.
4.  THE `ALLOWED_STATUSES` and `ALLOWED_TRACKER_STATUSES` lists in `utils/validation.py` SHALL be removed and their logic replaced by the Enums.

### Requirement 2: Comprehensive Codebase Refactoring

**User Story:** As a maintainer, I want all hardcoded status strings in the Python code replaced with Enum members, so that the code is more readable and less prone to bugs from typos.

#### Acceptance Criteria

1.  THE system SHALL use the `JobDbStatus` Enum in all database-related logic, including queries and updates within the `db/` directory.
2.  THE system SHALL use the `JobTrackerStatus` Enum in all tracker-related business logic, primarily `utils/tracker_policy.py`.
3.  THE system SHALL update all tool scripts in the `tools/` directory to use the appropriate Enums.
4.  THE system SHALL update all tests in the `tests/` directory to use the Enums for data setup and assertions.
5.  A codebase search for the old hardcoded status strings (e.g., `'shortlist'`, `'Reviewed'`) within `.py` files SHALL yield no results in application logic after the refactoring is complete.

### Requirement 3: Behavior and API Contract Parity

**User Story:** As an operator and API consumer, I want the application's behavior and API contract to be unchanged after the refactoring, so that existing workflows and clients are not broken.

#### Acceptance Criteria

1.  WHEN a tool is invoked via the API, ITS observable behavior and final output concerning job statuses SHALL be identical to the pre-refactor behavior.
2.  THE system's external API contract SHALL remain the same. Specifically, API endpoints will continue to accept and return statuses as plain strings. Pydantic or a similar layer will handle the conversion to/from internal Enums.
3.  ALL existing automated tests (`uv run pytest`) SHALL pass after the refactoring is complete.
