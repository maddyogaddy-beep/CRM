# CRM

DriveCentric BDC rules for Maddy at McCarthy Honda. Create short, useful customer drafts that answer real questions and earn replies and showroom visits.

## Canonical rule files

Load [rules.yaml](rules.yaml), then its listed files in order. [AGENTS.md](AGENTS.md) gives repository-aware Codex the same entry point. Do not copy the rules into this README or treat older uploads as a second configuration.

| File | Purpose |
| --- | --- |
| [SKILL.md](SKILL.md) | Sales workflow, customer evidence, draft creation, and output contract |
| [messaging.yaml](messaging.yaml) | Canonical voice, direct answers, conditional visit asks, and draft versus send review |
| [lead-source-playbooks.yaml](lead-source-playbooks.yaml) | Source hypotheses and neutral discovery questions |
| [daily-workplan.yaml](daily-workplan.yaml) | Existing recorded Workplan targets and counting distinctions |
| [Workplan reference](references/daily-workplan-operating-system.md) | Reconciliation using actual CRM evidence |
| [Convo goals](Convo%20goals) | Historical August 2026 planning model and snapshot |
| [assistant-coordination.yaml](assistant-coordination.yaml) | Five-chat private handoffs without sharing browser access |

Maddy's current instructions override repository defaults. messaging.yaml owns voice and draft preparation. Keep customer identity and claims evidence-based. A draft is an output for Maddy to review and send, not an executed CRM action.

## Draft behavior

Answer the latest customer question first. Introduce Maddy only when the sender needs identifying. Use one relevant fact and one easy next question; do not pad a short answer to meet a word or character floor. Tie price or payment discussions to a conditional visit question without implying an unapproved deal is guaranteed. Provide known approved prices when asked.

Recent contact, a requested-later date, unresolved ownership, or incomplete history may require a held draft. Missing optional source information or current price proof should narrow what the draft says. Repeated unanswered outreach should change the approach. These conditions do not automatically justify returning no copy. Wrong-customer identity and channel opt-outs still affect the channel and customer for which copy can be prepared.

## Five assistant chats

Share verified customer packets, draft assignments, review flags, and evidence timestamps through the existing private project or authorized private artifact. Each chat retains its existing access; no browser cookies, tab handles, credentials, or sessions are shared. Drafting and reviewing can use a sufficient packet without browser access. Use one active draft author per customer and channel so the chats improve a common queue rather than duplicate it.

This is a coordination contract. No cross-chat connection, queue service, live CRM reader, or executable drafting engine is implemented in this repository. A connected runtime must actually load these files and provide the private handoff mechanism before synchronization can be claimed.

## Historical material

`archive/revised-closer-notes.txt` preserves the old conflicting persona notes as inactive source material. It is excluded from active rules and is not an installable skill. `visit-outreach-draft-queue-2026-08-12.md` is a dated report, not evidence of current inventory, customer status, counters, or current sending permission. Historical August conversion goals do not supply October targets.

## Validation

Install the development dependency with `python -m pip install -r requirements-dev.txt`, then run `python scripts/validate_rules.py`. Validation checks YAML, skill frontmatter, local dependencies, manifest consistency, and structured draft-only settings. It is a static repository check; it cannot prove a separate assistant loaded the files or a DriveCentric draft was created.

## Remaining external inputs

- The actual project or runtime configuration used by the five chats, its rule loader, and its private shared queue or handoff artifact.
- Current customer profiles and timelines or verified private packets, current contact and ownership status, and live Workplan counts for actual daily work.
- Current approved inventory, deal terms, and email signature when needed for a specific claim or send review. Their absence does not block a supported body draft that omits those details.
- A current monthly conversion goal if monthly planning is requested. The only monthly goal stored here is August 2026.

No operational batch sizes, cooldown durations, new monthly targets, or live connections have been invented to fill those gaps.
