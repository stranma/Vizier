# PRD: Vizier v2 -- Hermes-Based Province Orchestration

## Vision

Vizier is a secure software-organization layer built on top of **Hermes**.
One Vizier agent manages **provinces**: isolated work domains created from
reusable **firmans**. Each province has its own Pasha, workspace,
credentials, outbound access policy, and GitHub output.

Vizier is not trying to be a general-purpose agent runtime. Hermes provides
the runtime substrate: agent sessions, messaging, tools, memory, and
delegation. Vizier's product value is the province model, the security
boundaries, and the operator workflow around them.

## Product Boundary

**Hermes provides:**
- Agent runtime and session management
- Telegram integration and direct human-agent threads
- Tool calling and sub-agent execution
- Persistent memory and general runtime infrastructure

**Vizier provides:**
- Province lifecycle and realm management
- Firmans as reusable province templates
- Security mediation via Sentinel, proxy sidecars, and secret brokerage
- Pull-request-based delivery workflow
- Operator control over grants, appeals, and province termination

## Core Purpose

Sultan chats with Vizier on Telegram. Vizier creates provinces from firmans,
launches a Pasha for each province, and tracks the realm. Sultan can also
talk to a Pasha directly when the work requires clarification, reprioritizing,
or a decision. Pasha works inside the province and delivers a GitHub pull
request. Sentinel enforces network and credential boundaries around that work.

Telegram is for steering and approvals. GitHub is for review and merge.
The output is a pull request, not a visible spec workflow.

## Glossary

- **Firman** -- a reusable province template. Defines the province shape:
  workspace bootstrap, tools, Pasha instructions, and default outbound
  access policy.
- **Province** -- an instantiated firman. The isolation unit for one work
  stream, including its Pasha, workspace, privileges, and projects/repos.
- **Realm** -- the set of all provinces managed by Vizier.

## Design Constraints

- **Vizier is reactive.** It acts on Sultan commands and agent events. It does
  not invent work on its own.
- **Pasha has a direct line to Sultan.** Vizier owns province creation and
  realm coordination, but Sultan may message a Pasha directly for execution
  decisions.
- **Phase 1 is security-first.** Province isolation, outbound control,
  credential brokerage, and appeals are part of the initial product contract.
- **Enforcement must be deterministic.** No LLM sits in the hot path for
  network or credential enforcement.
- **Internal planning is an implementation detail.** Vizier or Pasha may use
  internal task decomposition, but the product contract is task -> province ->
  PR.
- **Telegram + GitHub only.** Other Hermes-supported channels are out of scope
  for the product contract in v2.
- **Provinces are long-lived.** A province may handle multiple tasks and PRs
  over time. Province lifecycle state must not be overloaded with task or PR
  progress.

## Phase 1 User Stories

### 1. Sultan gives Vizier a task

Sultan messages Vizier in Telegram: "Create a Python CLI tool that does X."
Vizier creates a province from the `hermes-firman`, provisions the
workspace and security boundary, launches Pasha, and tracks province state.

### 2. Sultan talks to Pasha directly

Sultan opens the Pasha thread: "Focus on the API first." Pasha adjusts. Sultan
can ask status, clarify requirements, or answer tradeoff questions directly.

### 3. Sultan reviews a PR

Pasha opens a GitHub pull request and notifies Sultan in Telegram. Sultan
reviews and merges in GitHub. If changes are requested, Pasha iterates in the
same province.

### 4. Sultan kills a runaway province

"Kill province X." Vizier stops the province and records the new state.

### 5. Sultan checks realm status

"What is active right now?" Vizier reports active provinces, basic status,
assigned Pashas, and whether any approvals are pending.

### 6. Proxy sidecar blocks an operation and Pasha appeals

Pasha attempts an outbound request outside the province allowlist. The proxy
sidecar blocks it. Pasha first tries alternatives. If no alternative works,
Pasha escalates to Sultan with what it tried, why the access is needed, and
what happens if the request is denied.

### 7. Sentinel brokers private repo access

Pasha needs access to a private dependency repo. Sultan approves the request.
Sentinel grants scoped repo access to that province only and records the grant.

### 8. Sentinel provisions an external API key

Pasha needs access to an API such as Stripe. Sultan approves scope and key
type. Sentinel grants the province the minimum needed access. Pasha can use
the credential through the proxy path without reading the raw secret.

### 9. Sentinel alerts Sultan

Sentinel detects suspicious outbound behavior or policy anomalies and alerts
Sultan directly in Telegram with enough detail to decide whether to revoke
access or kill the province.

## Later-Phase User Stories

These are part of the long-term direction, but not part of the initial product
contract:

- Vizier coordinates the same change across multiple provinces
- Vizier creates ad-hoc group channels for cross-province work
- Sultan requests detailed cost and budget reporting across the realm
- Vizier requests privileged host operations through a root daemon
- Rich-media workflows become a required product feature rather than a runtime
  convenience

## Province Lifecycle

Province state is infrastructure state, not task state.

Allowed province states:
- **creating** -- Vizier is instantiating the province from a firman and
  bringing up its runtime and security boundary
- **running** -- the province exists, Pasha is reachable, and the workspace
  and policy boundary are active
- **stopped** -- the province exists but is not currently running
- **failed** -- province startup or runtime has failed and operator attention
  is required
- **destroying** -- Vizier is tearing down the province and cleaning up its
  resources

Task execution state and pull request state are tracked separately from the
province lifecycle. A single running province may produce multiple tasks and
multiple PRs over time.

## Agents and Services

| Component | Where | Runtime | Role |
|-----------|-------|---------|------|
| **Sultan** | Telegram + GitHub | Human | Gives direction, reviews PRs, approves grants, kills provinces. |
| **Vizier** | Hermes | Hermes agent | Realm manager. Creates provinces from firmans, launches Pashas, tracks realm state, stops provinces. |
| **Pasha** | Per province | Hermes agent inside province workspace | Province governor. Executes the task, asks for decisions, and delivers PRs. |
| **Sentinel Core** | Host/service layer | Deterministic service | Owns policy, grants, allowlists, audit trail, and security decisions that must be enforced deterministically. |
| **Sentinel Assistant** | Hermes | Hermes agent | Optional operator-facing assistant for explaining policy, summarizing alerts, and preparing approval context. Never in the hot path. |
| **Proxy Sidecar** | Per province | Deterministic proxy | Enforces outbound allowlist and injects credentials for approved external requests. |
| **Secret Vault** | Host/service layer | Secret manager | Stores credentials and issues scoped access for province use. |

## Sentinel and Proxy Model

### Proxy Sidecar

The proxy sidecar is the real-time traffic gate. Every province's outbound
HTTP/HTTPS traffic is forced through its proxy sidecar. The proxy checks a
province-specific allowlist and injects credentials for approved requests.
Blocking and credential injection are deterministic.

### Sentinel Core

Sentinel Core manages the proxy sidecars' policy and the secret vault:
- default outbound allowlists from the firman
- province-specific grants approved by Sultan
- scoped repo and API credentials
- security audit trail
- anomaly detection inputs and operator alerts

Sentinel Core can block, grant, revoke, and alert. It does not write code or
operate as the province runtime.

### Sentinel Assistant

Sentinel Assistant is optional and operator-facing. It may:
- summarize alerts
- explain grant scope
- prepare approval context
- answer questions about why a request was blocked

Sentinel Assistant never decides or enforces policy in the hot path.

### Use But Not Read

Approved credentials are usable by the province through the proxy path, but
the raw secret is not exposed to Pasha as normal task context. The intended
security property is that the agent can perform approved external actions
without casually reading or copying the credential value.

Raw credentials must not be passed through normal agent prompt context,
standard workspace files, or default runtime environment variables unless
there is an explicit operator-approved break-glass path.

### Alerts vs Enforcement

- **Proxy Sidecar enforces** outbound traffic policy in real time
- **Sentinel Core manages** grants, revocations, allowlists, and credential
  scope
- **Sentinel Core and Sentinel Assistant surface alerts** and operator context
- **Vizier stops provinces** when Sultan decides the province should be
  terminated

## Security Boundaries

Phase 1 requires four boundaries:

1. **Province isolation** -- each province has its own workspace, Pasha, and
   privileges.
2. **Egress filtering** -- all outbound traffic flows through the proxy
   sidecar and is checked against a deterministic allowlist.
3. **Credential brokerage** -- Sentinel grants credentials per province with
   minimal scope and revocation support.
4. **Operator approval** -- access outside the existing province policy must
   be approved by Sultan.

## Firmans

Firmans are first-class product concepts. A firman defines:
- province bootstrap
- Pasha operating instructions
- default tools available inside the province
- default outbound policy
- default repo/workspace structure for that work type

Vizier is firman-agnostic. It instantiates provinces from firmans and tracks
their lifecycle. Different work types should use different firmans.

Phase 1 requires one canonical production firman: **`hermes-firman`**.
`hermes-firman` is the reference province template for end-to-end validation
of the Phase 1 system. It must include:
- Hermes-native province bootstrap
- a Pasha instruction artifact that defines the Pasha's role, operating rules,
  and delivery contract inside the province
- default tool set for general software tasks
- default outbound allowlist
- GitHub pull-request delivery contract

Additional specialized firmans are deferred until the core province lifecycle
is proven with `hermes-firman`.

For Phase 1, the minimum firman contract is:
- workspace bootstrap contract
- Pasha instruction artifact
- tool and policy manifest
- default outbound allowlist
- GitHub repo, branch, and PR behavior

Phase 1 assumes `hermes-firman` lives in its own repository and is versioned
independently from Vizier.

## GitHub Access Model

Pasha opens pull requests using province-scoped GitHub credentials brokered by
Sentinel. GitHub access must be:
- scoped to the specific repo or repos approved for that province
- revocable without destroying the province
- separate from Vizier's own control-plane identity

If additional repo access is required after province creation, Sultan must
approve the scope increase and Sentinel must update the province grant.

## Telegram and GitHub Structure

Phase 1 requires:
- **Vizier thread** -- Sultan <-> Vizier for task delegation, realm status,
  approvals overview, and province termination
- **Pasha thread** -- Sultan <-> Pasha for direct execution guidance and
  decision-making
- **Sentinel thread** -- Sultan <-> Sentinel Assistant for security alerts,
  grant explanations, and approval context

GitHub remains the review surface:
- Pasha opens a PR
- Sultan reviews and merges

Cross-province group channels are explicitly deferred.

## Work Output

The required output is a **GitHub pull request**.

Pasha may use any internal execution process needed to complete the work, but
the operator-facing contract is:
- task assigned
- province created
- work executed inside province
- PR opened for review

## Architecture

```text
Sultan (Telegram + GitHub)
  |
  +---> Vizier (Hermes agent, reactive realm manager)
  |       |-- creates provinces from firmans
  |       |-- launches/stops Pashas
  |       |-- tracks realm state
  |
  +---> Pasha (Hermes agent, direct thread with Sultan)
  |       |-- works inside province workspace
  |       |-- asks for decisions directly when needed
  |       |-- opens PRs on GitHub
  |
  +---> Sentinel Assistant (Hermes agent, optional)
  |       |-- summarizes alerts
  |       |-- explains grants and blocked requests
  |
  +---> Sentinel Core (deterministic service)
  |       |-- manages allowlists and grants
  |       |-- provisions scoped credentials
  |       |-- alerts on anomalies
  |
  +---> Secret Vault
  |
  +---> Province
          |
          +-- workspace created from firman
          +-- Pasha operates within province boundary
          +-- Proxy Sidecar enforces outbound policy
```

## Key Architectural Decisions

1. **Hermes is the runtime substrate** -- Vizier and Pasha are Hermes agents.
   Vizier does not re-implement generic agent runtime concerns.

2. **Provinces remain the main product abstraction** -- Vizier manages
   provinces, not just projects or chat sessions.

3. **Firmans remain first-class** -- templates are part of the product model,
   not an implementation footnote.

4. **Direct Sultan <-> Pasha communication is required** -- Vizier remains the
   realm manager, but execution decisions may happen in the Pasha thread.

5. **Security is a first-phase feature** -- province creation without outbound
   controls and scoped credential brokerage is not sufficient for v2.

6. **Sentinel is hybrid** -- deterministic enforcement plus optional Hermes
   assistant. No LLM in the hot path.

7. **Telegram + GitHub are the only required channels** -- other Hermes
   channels are deferred.

8. **PRs are the output contract** -- internal decomposition is allowed, but
   the visible workflow is not spec-first.

## Deferred from the Initial Contract

- Root daemon and privileged host execution
- Cross-province fanout and shared coordination channels
- Broad budget and cost reporting
- Rich-media workflows as a required feature
- General multi-channel support beyond Telegram + GitHub

## Non-Goals

Phase 1 is not:
- a general-purpose multi-channel agent platform
- autonomous self-starting work orchestration
- a broad catalog of specialized firmans
- a privileged host automation system
- a full cost and finance management product

## Verification

**Phase 1 happy path:**
1. Sultan messages Vizier: "Build X"
2. Vizier creates a province from `hermes-firman`
3. Pasha starts work inside the province
4. Sultan gives one direct clarification to Pasha
5. Pasha opens a PR
6. Sultan reviews in GitHub
7. Sultan tells Vizier to stop the province

**Phase 1 firman validation:**
1. Vizier instantiates a province from `hermes-firman`
2. The province boots a Hermes-native Pasha successfully
3. A small software task completes end to end
4. The task results in a GitHub pull request
5. The firman's default proxy and credential policy is enforced

**Phase 1 security path (API access):**
1. Pasha attempts an outbound API call outside policy
2. Proxy sidecar blocks it
3. Pasha tries alternatives and then appeals
4. Sultan approves limited access
5. Sentinel updates policy and provisions scoped credential use
6. Pasha completes the task without receiving the raw secret as normal task
   context

**Phase 1 security path (suspicious behavior):**
1. Province generates anomalous outbound behavior
2. Sentinel detects it and alerts Sultan
3. Sultan decides whether to revoke access or kill the province
4. Vizier can stop the province on command
