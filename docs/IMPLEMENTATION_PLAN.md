# Vizier v2 -- Phase 1 Implementation Plan

## Summary

Phase 1 starts by making **Vizier itself run correctly on Hermes** before
building provinces, firmans, or Pasha runtime behavior.

The Phase 1 sequence is:

- Hermes-hosted Vizier operator shell comes first
- Sentinel is added next as Vizier's initial control-plane security boundary
- province modeling and province APIs come after Hermes + Sentinel are working
- firman bootstrap and province lifecycle come after the province model exists
- Hermes-native Pasha runtime comes after the province and firman foundations
- local-development and GitHub Actions integration testing are required from the
  first Hermes-Vizier milestone onward

This plan replaces the previous OpenClaw-first and province-first sequencing as
the active implementation source of truth.

## Existing Assets To Reuse

The current codebase already contains useful Phase 1 foundations:

- FastMCP server structure and test setup in `vizier-mcp`
- `realm.json` persistence patterns that can be adapted to provinces later
- structured logging and health checks
- Docker packaging and Docker Compose patterns
- deployment workflow structure in GitHub Actions

These should be reused where they save time.

OpenClaw-specific runtime configuration is not an active Phase 1 foundation. It
may be used as reference material only while Hermes replaces it.

## Phase 1 Deliverables

### 1. Hermes-Hosted Vizier Operator Shell

**Goal:** deploy Vizier as a Hermes agent with the correct minimal
control-plane privileges.

**Deliverables:**
- Hermes installation/provisioning contract for local development, CI, and deployment
- Vizier Hermes agent definition, SOUL/instructions, and runtime configuration
- Deployment wiring that starts Hermes-hosted Vizier instead of OpenClaw-hosted Vizier
- Minimal control-plane privilege configuration for Vizier
- Integration test suite for local development and GitHub Actions
- Removal of OpenClaw from the active Phase 1 deploy/test path

**Required behavior:**
- Hermes can start Vizier successfully
- an operator can send Vizier a basic message through Hermes and receive a valid response
- Vizier can access the MCP/tool surface needed for health, help, and status behavior
- Vizier runs with only the control-plane privileges needed to operate itself
- Pasha-on-Hermes is not required in this milestone

**Acceptance criteria:**
- local development can run a Hermes-Vizier integration suite without production secrets
- GitHub Actions can install/provision Hermes and run the same Hermes-Vizier integration suite
- the packaged Phase 1 stack boots with Hermes-hosted Vizier and passes smoke checks
- OpenClaw is no longer part of the active Phase 1 runtime validation path

### 2. Sentinel Baseline For Vizier Control Plane

**Goal:** establish the first deterministic security boundary around Vizier
before province runtime work begins.

**Deliverables:**
- Sentinel policy contract for Vizier's control-plane privileges
- deterministic allow/deny path for Vizier control-plane actions
- audit entries for allow, deny, and revoke events relevant to Vizier
- integration tests proving privilege enforcement

**Required behavior:**
- explicitly allowed Vizier control-plane actions succeed
- broader host or network actions outside Vizier's granted scope are denied
- denials are deterministic and auditable
- missing permission defaults fail closed

**Acceptance criteria:**
- integration tests prove allowed actions succeed and denied actions fail
- denied actions produce auditable records
- Hermes-hosted Vizier remains operational under the enforced privilege model

### 3. Province Domain Model

**Goal:** replace project-centric realm state with province-centric state after
Hermes-hosted Vizier and Sentinel are working.

**Deliverables:**
- Province model replacing the current project model
- Province lifecycle enum with exactly:
  `creating`, `running`, `stopped`, `failed`, `destroying`
- Realm state updated to store provinces, firman reference, workspace path,
  runtime metadata, and security metadata
- Public tool surface rewritten around provinces rather than projects

**Required behavior:**
- province lifecycle is infrastructure state only
- task status and PR status are not encoded into province state
- a province can remain `running` across multiple tasks and PRs
- project-era realm state is not migrated forward

**Acceptance criteria:**
- realm persistence can create, read, list, and update province lifecycle state
- invalid province state transitions return structured errors
- old project-era state is left behind rather than migrated

### 4. Firman Contract + `hermes-firman`

**Goal:** make firmans concrete and testable once provinces exist.

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
- Vizier can create a province from `hermes-firman` without manual setup
- the firman version/reference used for province creation is recorded in realm state

**Acceptance criteria:**
- province creation from `hermes-firman` produces a bootable workspace
- missing or malformed firman artifacts fail during `creating` with clear errors

### 5. Province Workspace + Container Lifecycle

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

### 6. Hermes Runtime Integration For Pasha

**Goal:** add Hermes-native execution inside provinces after the Hermes-hosted
Vizier control plane, Sentinel baseline, province model, and firman bootstrap
are in place.

**Deliverables:**
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

### 7. Secret Brokerage + GitHub Access

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

### 8. Appeals, Alerts, and Operator Actions

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

### 9. Verification Path

**Goal:** prove the Phase 1 contract end to end with layered automated testing
that works in local development and GitHub Actions.

**Required automated test layers:**
- unit tests for models, manager logic, validation, and server behavior
- Hermes-Vizier integration tests using Hermes local test mode and no production secrets
- packaged stack smoke tests validating the deployed Hermes-hosted Vizier shape
- later end-to-end tests covering province, firman, and Pasha flows as those
  deliverables land

**Required end-to-end scenarios:**
- Hermes-Vizier shell path:
  Hermes starts Vizier -> operator sends a basic message -> Vizier responds ->
  health/status path succeeds
- Sentinel baseline path:
  allowed control-plane action succeeds -> denied action fails -> audit entry recorded
- happy path:
  task -> province from `hermes-firman` -> running Pasha -> direct clarification
  -> PR opened -> province stopped
- API grant path:
  blocked external call -> appeal -> grant -> successful completion
- suspicious behavior path:
  anomalous outbound activity -> alert -> Sultan decision -> province stop

**Acceptance criteria:**
- the Hermes-Vizier integration suite runs locally and in GitHub Actions
- the packaged stack smoke suite runs locally and in GitHub Actions
- each later end-to-end scenario is covered by automated tests where possible
  and by one documented manual runtime validation flow where external systems
  are required

## Delivery Order

Implement in this order:

1. Hermes-hosted Vizier operator shell
2. Sentinel baseline for Vizier control plane
3. Province model and province API cutover
4. Firman contract and `hermes-firman`
5. Province workspace/container lifecycle
6. Hermes runtime integration for Pasha
7. Secret brokerage and GitHub credential flow
8. Appeals, alerts, and operator actions
9. End-to-end verification and deployment simplification

## Explicit Non-Goals For This Plan

Do not implement as part of Phase 1:

- OpenClaw as an active runtime dependency for the target architecture
- Pasha-on-Hermes before Hermes-hosted Vizier and Sentinel are stable
- migration of old project-era realm state into province state
- cross-province coordination or ad-hoc group channels
- root daemon or privileged host execution
- broad cost reporting
- rich-media requirements
- multi-channel support beyond Telegram + GitHub
- a catalog of specialized firmans beyond `hermes-firman`

## Notes On Migration

- Existing OpenClaw-specific configuration can be removed from the active
  runtime and deployment path once Hermes-hosted Vizier replaces it.
- Existing realm/container code should be refactored toward provinces where it
  saves time, rather than rewritten from zero without reason.
- Project-era realm state is left behind rather than migrated.
- Documentation and deployment configuration must be updated in the same phase
  as the Hermes cutover so the repo does not advertise OpenClaw as the active
  architecture once implementation starts.
