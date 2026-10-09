# Daily Workplan operating reference

This reference consolidates the targets and reconciliation rules already recorded in the repository's [SKILL.md](../SKILL.md) and [Convo goals](../Convo%20goals). The machine-readable targets are in [daily-workplan.yaml](../daily-workplan.yaml). It does not supply a new cadence, batch size, current-month goal, or current CRM counts.

## Recorded targets and counting

Track all assigned Workplan tasks, 50 unique customers called, 150 unique customers sent CRM-counted emails, 150 unique customers sent CRM-counted SMS messages, and 2 appointments agreed to and recorded. Use the latest DriveCentric My Workplan counters and underlying customer records as evidence. Keep drafts, pending work, completed activity, and pipeline events separate. Keep assistant-executed activity at zero in DRAFT_ONLY.

Track CRM box counts and verified unique-customer counts separately. Do not treat duplicate activities, teammate activity, or a historical queue as proof of Maddy's current progress. Do not count an appointment question as an appointment set. Report unknown counters and unknown counting mappings explicitly.

## Preparation and reconciliation

1. Record the local work date, evidence timestamp, source, completed and assigned tasks, labeled CRM counts, and verified unique-customer counts where available.
2. Answer fresh inbound first. Then prioritize proposals, unsold visits and no-shows, engaged customers, and lead discovery using the verified context.
3. Produce relevant drafts and call openers. Recent contact or an explicit requested-later date can hold a draft for later review. A price, payment, trade, credit, or comparison objection calls for useful copy, not an automatic skip.
4. After each reviewed batch, refresh the available CRM evidence and report completed activity separately from drafts prepared. Do not impose a batch size absent an active instruction.
5. Report remaining deficits, eligible capacity, shortages by channel, held or blocked records with reasons, and the next useful queue. Never lower recorded targets to declare completion or invent activity to fill them.

Calculate task remaining as `max(assigned - completed, 0)`. Calculate a minimum box deficit as `max(target - box_count, 0)` when the box count is known. Calculate an exact unique-customer deficit only when the relevant distinct-customer evidence is known; otherwise report `UNKNOWN`. Do not substitute a box deficit for an unknown unique-customer deficit.

## Report fields

Include `workplan_date`, `timezone`, `verified_at`, `source`, `action_mode`, `workplan_tasks`, `crm_box_counts`, `verified_unique_customer_counts`, `remaining_deficits`, `pending_drafts`, `assistant_executed_activity`, `capacity_shortfalls`, `held_or_blocked_by_reason`, and `next_queue`. Use `UNKNOWN` for absent evidence. Declare verified completion only when every required task and metric is supported by current CRM evidence.

Keep Workplan targets, assignment information, review flags, and performance comparisons out of customer copy. Customer messages should answer the customer's question and make one useful next step easy.
