# Vizier v2 -- Phase 1 Implementation Plan

## Summary

Phase 1 implements the smallest production slice of the new PRD:

- Hermes is the runtime substrate for Vizier and Pasha
- provinces are long-lived and instantiated from `hermes-firman`
- Telegram is the operator surface and GitHub is the review surface
- Sentinel and proxy sidecars enforce the security boundary
- the visible workflow is task -> province -> PR

This plan replaces the previous OpenClaw/spec-centric roadmap as the active
implementation source of truth.

## Existing Assets To Reuse

The current codebase already contains useful Phase 1 foundations:

- `realm.json` persistence and realm manager patterns
- container lifecycle tooling around devcontainers and Docker
- structured logging and health checks
- MCP server structure and test setup
- deployment packaging and Docker Compose patterns

These should be adapted, not discarded blindly.

## Phase 1 Deliverables

### 1. Province Domain Model

**Goal:** replace project-centric realm state with province-centric state.

**Deliverables:**
- Province model replacing or superseding the current project model
- Province lifecycle enum with exactly:
  `creating`, `running`, `stopped`, `failed`, `destroying`
- Realm state updated to store provinces, firman reference, workspace path,
  runtime metadata, and security metadata
- Realm tool surface rewritten around provinces rather than specs/projects

**Required behavior:**
- province lifecycle is infrastructure state only
- task status and PR status are not encoded into province state
- a province can remain `running` across multiple tasks and PRs

**Acceptance criteria:**
- realm persistence can create, read, list, and update province lifecycle state
- invalid province state transitions return structured errors
- existing `realm.json` loading fails safely when older data is missing fields

### 2. Firman Contract + `hermes-firman`

**Goal:** make firmans concrete and testable in Phase 1.

**Deliverables:**
- Firman contract definition in code and docs
- Support for instantiating a province from a firman repository
- A canonical `hermes-firman` repository used as the first reference template
- Province bootstrap logic that consumes the firman contract

**Minimum `hermes-firman` contract:**
- workspace bootstrap contract
- Pasha instruction artifact
- tool and policy manifest
- default outbound allowlist
- GitHub repo, branch, and PR behavior

**Required behavior:**
- Vizier can create a province from `hermes-firman` without any manual setup
- firman version/reference used for province creation is recorded in realm state

**Acceptance criteria:**
- province creation from `hermes-firman` produces a bootable workspace
- missing or malformed firman artifacts fail during `creating` with clear errors

### 3. Hermes Runtime Integration

**Goal:** replace OpenClaw-specific execution assumptions with Hermes-native ones.

**Deliverables:**
- Hermes runtime configuration for Vizier
- Hermes-native Pasha launch model inside a province workspace
- Telegram thread mapping for Vizier and Pasha
- Minimal operator workflow for:
  task assignment, direct Pasha clarification, PR notification, province stop

**Required behavior:**
- Vizier owns province creation and stop operations
- Pasha has a direct Sultan communication line
- a running province means Pasha is reachable and the workspace is active

**Acceptance criteria:**
- Sultan can assign a task to Vizier through Telegram
- Vizier can launch a Pasha for a newly created province
- Sultan can send a direct clarification to that Pasha

### 4. Province Workspace + Container Lifecycle

**Goal:** adapt the existing container lifecycle code to long-lived provinces.

**Deliverables:**
- province create/start/stop/status operations
- workspace bootstrap from firman repo
- container metadata and reconciliation against actual runtime state
- explicit destroy flow for province teardown

**Required behavior:**
- `creating` covers bootstrap plus runtime bring-up
- `running` means container/workspace/security boundary are active
- `stopped` means province exists but runtime is not active
- `destroying` is reserved for teardown and cleanup

**Acceptance criteria:**
- create -> running works for `hermes-firman`
- running -> stopped works idempotently
- failed startup leaves province in `failed`
- destroy flow removes runtime resources and finalizes state cleanly

### 5. Sentinel Core + Proxy Sidecar

**Goal:** implement the deterministic Phase 1 security boundary.

**Deliverables:**
- per-province outbound allowlist model
- proxy-sidecar integration per province
- Sentinel Core service contract for:
  allowlist updates, repo grants, API grants, revocation, audit entries
- wiring between province metadata, firman defaults, and Sentinel grants

**Required behavior:**
- all province outbound HTTP/HTTPS traffic goes through the proxy sidecar
- firman defaults apply automatically at province creation
- province-specific grants extend policy only after operator approval

**Acceptance criteria:**
- blocked domain requests are denied deterministically
- approved domain requests succeed after grant application
- grant and revoke operations are recorded in an audit trail

### 6. Secret Brokerage + GitHub Access

**Goal:** enforce the "use but not read" credential model in Phase 1.

**Deliverables:**
- secret-vault integration contract
- province-scoped GitHub credentials
- province-scoped external API credentials
- explicit break-glass exclusion from normal runtime paths

**Required behavior:**
- raw credentials are not passed via normal prompt context, default env vars,
  or standard workspace files
- Pasha can use approved GitHub and API access through the intended broker path
- GitHub credentials are repo-scoped, revocable, and separate from Vizier's
  control-plane identity

**Acceptance criteria:**
- Pasha can open a PR using province-scoped GitHub access
- API access works only after Sentinel grant
- revoking access prevents further use without destroying the province

### 7. Appeals, Alerts, and Operator Actions

**Goal:** make the security-first workflow usable by Sultan.

**Deliverables:**
- blocked-operation appeal flow from Pasha to Sultan
- Sentinel Assistant surface for operator context
- alert path for suspicious outbound behavior
- Vizier action path for province termination

**Required behavior:**
- appeals include what was tried, why access is needed, and impact of denial
- Sentinel Assistant explains policy and grant scope but does not enforce it
- Vizier stops provinces only after Sultan decision, except for explicit future
  automated policies which are out of scope for Phase 1

**Acceptance criteria:**
- blocked repo/API access can be appealed and approved
- Sentinel can surface an alert tied to a specific province
- Sultan can terminate the alerted province through Vizier

### 8. Verification Path

**Goal:** prove the Phase 1 contract end to end.

**Required end-to-end scenarios:**
- happy path:
  task -> province from `hermes-firman` -> running Pasha -> direct clarification
  -> PR opened -> province stopped
- API grant path:
  blocked external call -> appeal -> grant -> successful completion
- suspicious behavior path:
  anomalous outbound activity -> alert -> Sultan decision -> province stop

**Acceptance criteria:**
- each scenario is covered by automated tests where possible and by one
  documented manual runtime validation flow where external systems are required

## Delivery Order

Implement in this order:

1. Province model and realm state migration
2. Firman contract and `hermes-firman`
3. Province workspace/container lifecycle
4. Hermes runtime integration for Vizier and Pasha
5. Sentinel Core and proxy-sidecar policy wiring
6. Secret brokerage and GitHub credential flow
7. Appeals, alerts, and operator actions
8. End-to-end verification and deployment updates

## Explicit Non-Goals For This Plan

Do not implement as part of Phase 1:

- cross-province coordination or ad-hoc group channels
- root daemon or privileged host execution
- broad cost reporting
- rich-media requirements
- multi-channel support beyond Telegram + GitHub
- a catalog of specialized firmans beyond `hermes-firman`

## Notes On Migration

- Existing OpenClaw-specific configuration, SOUL files, and spec-lifecycle
  assumptions should be treated as legacy and removed or isolated only when the
  Hermes path fully replaces them.
- Existing realm/container code should be refactored toward provinces where it
  saves time, rather than rewritten from zero without reason.
- Documentation and deployment configuration must be updated in the same phase
  as the runtime switch so the repo does not advertise OpenClaw as the active
  architecture once implementation starts.
