# Continue the CRM setup on Maddy's Mac

Use this task in the existing Codex project at `/Users/maddy/Documents/Codex/drivecentric-bdc-assistant`. That is the previously recorded project path; inspect it on the Mac before assuming its contents or the five chat workspaces are current.

## Ready task for Mac Codex

Continue my DriveCentric BDC setup using the current `main` branch of https://github.com/maddyogaddy-beep/CRM. Fix my actual drafting workflow so it answers customers' questions, avoids repeated introductions, and produces useful drafts even when send-time review is needed. Coordinate my five Codex chats through a private customer packet and draft queue without sharing browser sessions.

Inspect my existing project, instruction files, configuration loader, drafting engine, queue builder, dispatcher, and current tests first. Preserve my local changes. Reuse the current CRM repository fixes rather than doing that audit again. Install its versioned rule bundle using the reversible installer, reconcile older conflicting instructions, and update the executable code wherever necessary. Do not blindly replace existing runtime configs with a different schema.

Produce actual SMS and email copy from the verified customer context. Lead with the question or documented priority. Identify Maddy when needed; do not force an introduction in every established thread. Keep copy concise without minimum-length padding. Answer known approved numbers directly. For unapproved price or payment goals, use a conditional visit ask without implying a confirmed offer. Timing, repeated questions, missing optional source data, and ordinary sales objections should not cause empty draft outputs. Distinguish held drafts from unresolved customer identity and opted-out channels.

Verify that the five chats read the same rule version and coordinate customer/channel assignments in an actual private shared location. Inspect existing worktrees and use the actual shared project or private state location. A file copied into one worktree is not evidence that all five chats have it. Keep each chat's browser access independent. A verified customer packet should let a drafting chat work without another browser setup.

Test the current executable behavior with customer fixtures. Keep current customer data and private queues out of the public repository. Do not send messages or mutate CRM records. Report actual copy produced, review flags, rule version loaded, and any remaining live-access gap. Do not claim completion based only on instructions or a passing configuration parser.

## Reversible installation

Use Python 3.10 or newer with [requirements-dev.txt](requirements-dev.txt) installed in a suitable environment. Keep this repository in a separate checkout, inspect the installer first, and run its dry-run against the existing project:

```bash
python3 scripts/install_mac_rules.py --project /Users/maddy/Documents/Codex/drivecentric-bdc-assistant
```

Apply the reviewed local instruction-and-bundle changes:

```bash
python3 scripts/install_mac_rules.py --project /Users/maddy/Documents/Codex/drivecentric-bdc-assistant --apply
```

The installer preserves existing engine/config files, backs up replaced instructions and bundles, and distinguishes rule installation from engine integration. Follow its printed backup information to undo its managed changes. Install development dependencies only in the project's existing suitable Python environment or an isolated virtual environment. The dependency list is [requirements-dev.txt](requirements-dev.txt).

Treat `.crm-rules` as an installed snapshot. Reinstallation replaces its managed files with the canonical source and backs up any local edits first. Make lasting rule changes in the CRM source; review the dry-run and backups before replacing a locally modified snapshot.

After installation, explicitly reread the project instructions and the installed manifest in each existing chat, or start a fresh session. Check the metadata in `.crm-rules/install-metadata.json` to compare the source revision and file fingerprint across the five workspaces. The `runtime_updated` field remains `false`: the installer does not change executable drafting code.

The canonical files are mapped in [rules.yaml](rules.yaml), with coordination in [assistant-coordination.yaml](assistant-coordination.yaml). The recorded August conversion goal remains historical. Do not infer an October goal, cooldown interval, or batch size.

## Evidence from accessible older snapshots

These are inspection leads, not proof of the current Mac installation:

- In one Python snapshot, `src/drivecentric_bdc/messaging/drafting.py` constructs `Hi {name}, it's Maddy with McCarthy Honda.` unconditionally in `draft_message()`.
- `src/drivecentric_bdc/reporting/runner.py` returns early for ineligible and manual-review records before producing draft copy, and leaves `safe_fallback_message` empty.
- `src/drivecentric_bdc/config.py` validates messaging rules, but the observed drafting function does not consume the messaging configuration.
- The snapshot's Workplan model rejects extra fields and requires a different schema. The restored CRM Workplan file is a supported rule source, not a drop-in replacement for that model.
- The observed integration has fixture readers and resumable checkpoint files. No live reader or concurrency-safe five-chat assignment service was verified.
- Previously named Mac queue scripts `build_drivecentric_agent_queue.py` and `dispatch_drivecentric_agent_queue.py` were absent from the accessible snapshots. Look for their current versions on the Mac rather than inventing their interfaces.

## Verification checklist

- Known approved price: draft answers the price and asks one useful visit question.
- Established thread: draft starts with relevant content rather than a repeated introduction.
- Same-day teammate outreach: relevant copy is still prepared with a separate review flag, unless the task explicitly requests only customers unattempted today.
- Requested future follow-up: useful copy is prepared now and held for the customer's timing.
- Missing optional payload or signature: supported copy is produced; absent details are omitted or flagged.
- Unknown inventory or deal terms: no invented availability or financial promise.
- Unresolved identity or channel opt-out: no wrong-customer or prohibited-channel outreach is created.
- Two chats claim the same customer/channel: the shared assignment mechanism resolves the collision without sharing browser access.
- No generated drafts count as sent CRM activity; `total_sent=0`.

Codex discovers project guidance through AGENTS files; overrides and nested instructions affect which defaults are active. Existing worktrees have separate file copies. Inspect those facts on the Mac before calling all five chats updated. Official references: [AGENTS discovery](https://learn.chatgpt.com/docs/agent-configuration/agents-md) and [Git worktrees](https://learn.chatgpt.com/docs/environments/git-worktrees).
