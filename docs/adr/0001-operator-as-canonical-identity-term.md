# Operator as the canonical identity term

Date: 2026-07-03

## Status

Accepted

## Context

Every personal-data partition in the system — health programs, the user record,
facts — is keyed to a single admin user. The code defaults to the literal string
`"operator"` (`HEALTH_PROGRAM_PK` and `IF_USER_PK` in `app/src/config.py`), and
test scripts hard-warn "Never run tests against `pk=operator`." The term needed a
canonical name that would not collide with anything else.

## Decision

Use **Operator** as the canonical term for the admin user IF serves, in the
glossary (`CONTEXT.md`) and in code partition keys. IF has exactly one Operator,
and all personal data belongs to them.

## Alternatives considered

- **admin** — rejected: overloaded across too many domains (database admin, Discord
  server admin, OS admin), and "admin" can literally appear inside a Discord
  username, creating collision/aliasing risk when matching identities.
- **user** — rejected: too generic. The portals use "user" for any authenticated
  visitor, a different concept from the single owner IF serves.

## Consequences

- `"operator"` is baked into DynamoDB partition-key defaults and test-guard
  scripts; renaming is a data migration, not an env-var flip.
- The Operator (this context) is the same human who holds the Athlete role in the
  powerlifting portal context; the two contexts name the same person differently
  by design.
