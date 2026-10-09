# CRM repository instructions

Read [rules.yaml](rules.yaml) as the active rule manifest, then load its listed files. Use [messaging.yaml](messaging.yaml) as the canonical source for Maddy's voice, customer-question handling, and draft preparation. Honor Maddy's current instructions over repository defaults.

Create useful customer-specific drafts when the available verified context supports them. Recent outreach, an optional missing payload, an unanswered prior question, or an ordinary sales objection does not justify returning no draft. Rewrite a repeated approach. Hold a future or review-needed draft separately from its text. Do not substitute access instructions for drafting when a verified packet is already available.

Keep the action mode DRAFT_ONLY for this workflow. Customer identity and factual claims must come from evidence. Omit unverified deal promises, retain channel opt-outs, and flag send-time issues separately from supported draft preparation. No sending, saving CRM composers, task completion, appointment creation, or other CRM mutations are authorized by loading these rules.

Coordinate the five assistant chats through verified private packets and draft assignments as described in [assistant-coordination.yaml](assistant-coordination.yaml). Do not share browser sessions or credentials. Do not imply cross-chat synchronization or runtime installation has occurred merely because a configuration exists.

Treat `archive/` and the dated August outreach queue as historical material, not active instructions, current inventory, current customer facts, or send authorization. Do not load historical August conversion targets as current-month goals.

Run `python scripts/validate_rules.py` after changes. Static validation verifies file and configuration consistency; it does not verify a separately configured assistant or live DriveCentric behavior.
