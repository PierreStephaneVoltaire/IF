# Context — IF (Intelligent Agent Service)

The ubiquitous-language glossary for the IF agent service — the API, its
infrastructure, the Discord bot, and the agentic flow. IF is a personal AI agent
that coordinates each request through Sol and native Specialists, remembers the
Operator across conversations, and delivers through multiple Channels.

## People & Identity

**Person**:
An authenticated participant. Person identity comes from trusted channel or gateway credentials, never from message text. The Operator is one Person; other Persons keep separate Conversation and memory scopes.

**Operator**:
The admin user IF serves. All personal data — Facts, health, finance, diary —
belongs to the Operator, and IF has exactly one.
_Avoid_: admin, user, account, owner (as a standalone noun)

**IF**:
The agent itself, modeled as an entity with its own identity, opinions, and
principles — distinct from the Operator. IF forms opinions about the Operator,
holds its own principles, and reflects on its own performance; it is not a
stateless tool.
_Avoid_: bot, assistant, model

## Memory

**Fact**:
A single remembered piece of knowledge, scoped to a Conversation. A Fact has a
category, a source (stated, observed, assessed, or derived), and a confidence.
Some Facts describe the Operator; others are IF's self-facts (its identity,
opinions, principles).
_Avoid_: user fact, memory entry, note

**Capability Gap**:
A remembered instance where IF lacked a needed capability. Gaps are scored by
frequency, recency, and impact; recurring gaps are promoted to tool suggestions.
_Avoid_: limitation, missing feature

## Behavior

**Directive**:
A versioned behavioral rule that shapes how IF acts, tiered by priority from
core identity to temporary adjustments. Core Directives apply to every request;
a Specialist receives only the Directive types relevant to it.
_Avoid_: rule, instruction, setting, prompt

**Specialist**:
A domain expert IF delegates work to, with its own focus, scoped tools, and
applicable Directive types. Sol delegates when useful through native Codex children; ordinary conversation needs no Specialist selection. A Specialist returns its result or a further Handoff request to Sol.
_Avoid_: agent (use IF for the agent), subagent, role

**Route**:
A historical classification term. The native coordinator now chooses how to handle a request without a compulsory classification or planning stage.
_Avoid_: mode, flow path

**Handoff**:
A Specialist's request for another Specialist to do part of the work. The
target is validated, the child Specialist runs, and the result is synthesized.
_Avoid_: delegation, sub-call, chaining

## Interaction

**Channel**:
A platform IF delivers through — Discord, OpenWebUI, or the HTTP API — each with
its own message flow.
_Avoid_: platform, interface, endpoint

**Conversation**:
An ongoing exchange between a Person and IF. The Person and stable Conversation ID identify one persistent Codex thread across messages and restarts. A Conversation keeps its own history, native turns and scoped Facts.
_Avoid_: session (portal domains use Session for a training day; auth uses it
for login sessions), thread, chat

## Cognition

**Reflection**:
IF's metacognitive layer: after conversations, periodically, and on demand, IF
detects behavioral patterns, forms or updates opinions, logs Capability Gaps,
and tracks the Operator's growth. Reflection is what lets IF hold a stable point
of view over time.
_Avoid_: analysis, review, self-evaluation

**Heartbeat**:
IF's proactive engagement: when a Channel has been idle past a threshold, IF
starts a Conversation from stored Facts, outside quiet hours and cooldown.
_Avoid_: ping, notification, cron
