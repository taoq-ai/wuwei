# Feature Specification: README and documentation site

**Feature Branch**: `039-readme-docs`  
**Created**: 2026-09-28  
**Status**: Ready

## User Scenarios & Testing

### User Story 1 - First workspace (Priority: P1)

A new user can discover what WUWEI does, install the plugin, and create a workspace using the README and docs alone.

**Independent Test**: Follow the install and init instructions in a fresh Claude Code workspace.

**Acceptance Scenarios**:

1. **Given** Claude Code and Python 3.11+, **when** the user follows Install and Quick start, **then** they can install the plugin and run `wuwei init`.
2. **Given** a reader looking for `/wuwei plan`, **when** they read Quick start, **then** its current availability and planned flow are clear.

### User Story 2 - Configure and understand (Priority: P2)

A workspace owner can find every shipped configuration key and its default, understand current roles, guards, memory, adapters, charter overrides, and security boundaries.

**Independent Test**: Compare the configuration page with the shipped template, and follow links from the site index.

**Acceptance Scenarios**:

1. **Given** the shipped config template, **when** the owner reads the configuration page, **then** every template key and default is documented.
2. **Given** a planned capability from the design, **when** it is mentioned, **then** it is labeled planned.

### User Story 3 - Recognize WUWEI (Priority: P3)

A reader sees a clear day-flow hero in their chosen color scheme and understands the name and product boundaries.

**Independent Test**: Open README in light and dark modes.

**Acceptance Scenarios**:

1. **Given** either color scheme, **when** the README renders, **then** the matching SVG shows the day flow and uses the brand accent.

### Edge Cases

- Installation instructions cannot assume the planned `/wuwei plan` skill exists yet.
- The site must be publishable from `docs/site/` even though GitHub Pages has no native source setting for that nested directory.

## Requirements

### Functional Requirements

- **FR-001**: README MUST show the light and dark hero, brand mark and meaning, product boundaries, install, and a working init quick start.
- **FR-002**: Docs MUST explain concepts, configuration, adapters and ports, charter overrides and promote, security integration and threat model 9.1.
- **FR-003**: Docs MUST cover every key in the shipped configuration template with its default.
- **FR-004**: Docs MUST distinguish shipped behavior from planned behavior.
- **FR-005**: A Pages workflow MUST publish the plain Markdown site from `docs/site/`.

## Success Criteria

- **SC-001**: A new user can install and initialize a workspace from the docs alone.
- **SC-002**: Every shipped template key is discoverable by exact name on the configuration page.
- **SC-003**: README hero renders in both color schemes.

## Assumptions

- `/wuwei plan` is not present on the current main baseline and is documented as planned. The acceptance request to run it cannot be met by documentation alone.
- Pages deployment uses GitHub Actions because the requested site directory is nested below `docs/`.

## Deferred

- Implementing the planner skill and runnable `/wuwei plan` belongs to the team feature work, not this documentation issue.
