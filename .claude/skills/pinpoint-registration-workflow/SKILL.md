---
name: pinpoint-registration-workflow
description: Staff workflow and state machine for registering, verifying, correcting, merging, splitting and retiring PINPOINT places. Use when building or changing registration forms, the review queue, verification, merge/split/retire flows, or bulk import.
---

# Registration and verification workflow

Only staff with the right role (see `pinpoint-rbac-audit`) run these flows. Each step is a service function that writes `place_event` + `audit_event` in one transaction (see `pinpoint-domain-model`).

## Place lifecycle

```
draft -> pending_verification -> active -> retired
                 |                  |-> merged (successor set)
                 v                  |-> split  (successors set)
              rejected (reason)
```

- `draft`: registrar is still editing. Not visible to anyone else, has **no public ID yet**. The ID is issued on submit so abandoned drafts never burn IDs.
- `pending_verification`: submitted, waiting in the verifier queue.
- `active`: verified; label printable, resolver works.
- `rejected`: back to the registrar with a mandatory reason; can be edited and resubmitted.
- `retired`, `merged`, `split`: terminal. IDs are never reused; the resolver returns a tombstone or redirect.

Add `draft`, `pending_verification` and `rejected` to the status enum by migration; the domain-model skill lists the base values.

## Flows

**House:** pick pin on satellite map, confirm accuracy, run the duplicate guard (15 m), enter label, address text and landmark, set visibility (default `private`), submit, ID issued, verifier approves.

**Apartment building:** one pin, building details (name, blocks/towers, floors), submit and verify. Then **add units** in bulk: a range generator ("101-110, 201-210") or a pasted list, with a preview and a duplicate-label check per parent. Each unit gets its own ID. Units become `active` with their building's verification, so no separate queue per unit.

**Correction:** any edit to location, label, type or visibility is a new event with `before/after`. Pin moves over 50 m need a verifier. The ID stays the same.

**Merge (duplicates):** registrar proposes "A is a duplicate of B" with a reason; a different verifier approves; A becomes `merged`, children re-parent to B, A's ID redirects to B.

**Split:** one place becomes several (for example a house divided). Verifier-approved; the old place becomes `split` with `successor_ids`; new places get new IDs.

**Retire:** place demolished or invalid. Reason required, verifier approves. Children are retired in the same transaction.

**Bulk import (CSV):** admin only. Dry-run first: validate every row, return a report (valid, duplicate-suspect, invalid with line numbers), commit only on explicit confirmation, all-or-nothing per file. Imported places land in `pending_verification`, never straight to `active`.

## Rules

1. The requester and the approver must be different people for verify, merge, split and retire.
2. Every transition is validated by a small state-machine function; illegal transitions raise a domain error that maps to 409.
3. Never skip the duplicate guard, including in bulk import.
4. Reasons are required text for reject, retire, merge, split and "different place" overrides.
5. The review queue is filtered to the verifier's jurisdiction and ordered oldest first, and shows distance to the nearest existing places.

## UI requirements

Stepper for registration; satellite map with draggable pin and accuracy circle; live DIGIPIN and locality preview; unit range generator with preview table; verifier queue with side-by-side map and diff of changes; every state designed (empty queue, validation errors, saving, conflict). Follow `pinpoint-ui-design`.

## Tests required

State-machine transition table (legal and illegal), four-eyes enforcement, ID issued only on submit, merge re-parenting and redirect, split successors, unit range expansion and duplicate labels, bulk-import dry-run vs commit atomicity, and a Playwright flow: register building, add units, verify, scan label.
