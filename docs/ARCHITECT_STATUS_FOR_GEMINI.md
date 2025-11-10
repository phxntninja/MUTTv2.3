# MUTT v2.5 — Architect Status & Review Protocol (for Gemini)

Purpose
- Provide a crisp status and a safe, chunked review flow to avoid context overflows.
- Define exactly what to read, in what order, with tight output contracts per step.

Current Status (TL;DR)
- Delivery: Phases 1–3 are complete (incl. backpressure, remediation, SLOs).
- Canonical handoff: docs/PHASE_3_HANDOFF_TO_ARCHITECT.md:1
- Live plan: CURRENT_PLAN.md:1 (Phase 4 now in progress; Phase 5 pending).
- Status tracker: AI_COORDINATION_STATUS.md:1 (aligned to the above).

Key Artifacts (read-only context)
- CURRENT_PLAN.md:1 — Unified next steps (authoritative going forward).
- docs/PHASE_3_HANDOFF_TO_ARCHITECT.md:1 — What shipped in Phase 3 and breaking changes.
- docs/ALERTER_BACKPRESSURE.md:1 — Operator guide for queue-depth shedding.
- docs/SLOs.md:1 — SLO approach, endpoint, and recording rules pointer.
- README.md:1 — Product overview, architecture, and pointers.
- ai/handoffs/*_completed.md — Archived historical handoffs (do not re-ingest unless asked).

Quick Links (clickable paths)
- CURRENT_PLAN.md:1
- docs/PHASE_3_HANDOFF_TO_ARCHITECT.md:1
- docs/ALERTER_BACKPRESSURE.md:1
- docs/SLOs.md:1
- AI_COORDINATION_STATUS.md:1
- README.md:1

What We Need From You (Gemini)
- Validate architecture continuity from Phase 3 to Phase 4.
- Call out risks, missing decisions, or inconsistencies.
- Recommend any surgical adjustments to plan scope or order.
- Keep responses tightly scoped per chunk (see Output Contract).

Output Contract (per step)
- Length: ≤ 8 bullets, ≤ 120 words total.
- Structure: “Findings”, “Risks/Questions”, “Actionable Nudge (if any)”.
- No code or rewrites unless explicitly prompted in that step.
- If context is insufficient, ask 1–2 specific questions, then stop.

Chunked Review Flow (follow in order)
1) Read CURRENT_PLAN.md:1
   - Goal: Confirm next-step scope (Phase 4/5) and cross-cutting follow-ups.
   - Focus: Are objectives independent and sequenced sanely? Any missing dependencies?
   - Output: Findings/Risks/Nudge only.

2) Read docs/PHASE_3_HANDOFF_TO_ARCHITECT.md:1
   - Goal: Validate what’s delivered and breaking changes.
   - Focus: Backpressure keys, metrics label normalization, SLO endpoint specifics, deployment updates.
   - Output: Any compatibility risks for Phase 4; confirm observability baselines are adequate.

3) Read AI_COORDINATION_STATUS.md:1
   - Goal: Ensure the status and workflow align with steps (1) and (2).
   - Focus: Role assignments, “Next Steps”, and link correctness to CURRENT_PLAN.md.
   - Output: Any contradictions; list the single source of truth for planning.

4) Read docs/ALERTER_BACKPRESSURE.md:1 and docs/SLOs.md:1
   - Goal: Operator-facing clarity check.
   - Focus: Key tunables, metrics, and runbooks are actionable and consistent.
   - Output: Any unclear operator guidance; propose 1 improvement (max).

5) Skim README.md:1 (only ToC + Overview + Monitoring + What’s New in v2.5 sections)
   - Goal: Ensure top-level onboarding points to the right docs.
   - Output: List missing quick links (if any) and stop.

6) Optional (on request only): Inspect code entry points for Phase 4 touchpoints
   - services/web_ui_service.py:1 — API versioning, audit CRUD integration points.
   - services/audit_logger.py:1 — Helper surface is adequate for CRUD hooks.
   - Output: Gaps only; defer any code suggestions unless explicitly requested.

Ready-to-Copy Micro‑Prompts (use verbatim)
- Step 1 (Plan): “Read CURRENT_PLAN.md:1. In ≤8 bullets/≤120 words, provide Findings, Risks/Questions, and one Actionable Nudge. If insufficient context, ask max 2 clarifying questions and stop.”
- Step 2 (Phase 3): “Read docs/PHASE_3_HANDOFF_TO_ARCHITECT.md:1. In ≤8 bullets/≤120 words: compatibility risks for Phase 4; confirm observability baselines; one Nudge.”
- Step 3 (Status): “Read AI_COORDINATION_STATUS.md:1. In ≤8 bullets/≤120 words: identify contradictions vs plan/phase-3 handoff; state the single source of truth.”
- Step 4 (Ops Guides): “Read docs/ALERTER_BACKPRESSURE.md:1 then docs/SLOs.md:1 (separately). For each file, ≤6 bullets/≤100 words: unclear operator guidance and one improvement.”
- Step 5 (README): “Read README.md:1 (ToC, Overview, Monitoring, What’s New v2.5 only). In ≤5 bullets, list missing quick links and stop.”
- Optional Step 6 (Code touchpoints): “Skim services/web_ui_service.py:1 and services/audit_logger.py:1 (separately, ≤200 lines each window). Report only gaps blocking Phase 4; no code suggestions.”

Anti‑Crash Guardrails
- Never ingest more than one file per step.
- If a file is large, process in windows of ~200 lines (1→200, 201→400, …). Stop between windows.
- If the output would exceed the contract, summarize first, then ask to proceed.
- Do not reopen any *_completed.md handoffs without explicit instruction.

Glossary & Canonical Keys
- Redis queues: `mutt:ingest_queue`, `mutt:alert_queue`, `mutt:dlq:alerter`, `mutt:dlq:dead`
- Alerter backpressure config (DynamicConfig):
  - `alerter_queue_warn_threshold`, `alerter_queue_shed_threshold`
  - `alerter_shed_mode` = `dlq|defer`, `alerter_defer_sleep_ms`
- Normalized metric labels: `status={success|fail}`, low-cardinality `reason`
- Web UI SLO endpoint: `GET /api/v1/slo` (requires `PROMETHEUS_URL` env)
- Prometheus recording rules example: `docs/prometheus/recording-rules-v25.yml`

SLO Query Reference (Prometheus)
- Ingestor availability: `sum(rate(mutt_ingest_requests_total{status="success"}[$window])) / sum(rate(mutt_ingest_requests_total[$window]))`
- Forwarder availability: `sum(rate(mutt_moog_requests_total{status="success"}[$window])) / sum(rate(mutt_moog_requests_total[$window]))`
- Window hours from DynamicConfig: `slo_window_hours`


Known Open Decisions (seek your guidance)
- API versioning strategy details (header format, decorator pattern, deprecation policy cadence).
- Audit log API filtering defaults and pagination standards.
- Retention enforcement cadence and visibility (Prometheus rules vs. logs only).

Acceptance for Your Review
- Your reviews adhere to the Output Contract per step.
- You reference files by path and starting line (e.g., CURRENT_PLAN.md:1).
- You identify contradictions or missing links and propose a minimal fix.

End State We’re Driving Toward
- Phase 4 scope validated and unblocked (versioning + audit visibility).
- Operator docs solid for backpressure and SLOs; quick links accurate.
- Any gaps queued as concise issues or doc tweaks, not large rewrites.

Architect Sign‑off Checklist (use to conclude)
- Phase 4 objectives validated; no blocking dependencies.
- Observability baselines sufficient (metrics, SLOs, recording rules).
- Backpressure config keys and behavior understood/approved.
- README links point to plan, handoff, ops guides.
- Open decisions listed with one recommendation each or “defer”.
- No contradictions between status, plan, and handoff docs.

Hand‑off Protocol
- If all steps are green, deliver a final “Architect Sign‑off” note (≤ 6 bullets) and stop.
- If any step fails contract (context limits, gaps), stop and request the next smallest input.

Contacts
- Implementation: OpenAI Codex (active on Phase 4)
- Coordinator/Architect Doc: docs/PHASE_3_HANDOFF_TO_ARCHITECT.md:1
- Live Plan Owner: CURRENT_PLAN.md:1

Escalation Path
- If any step risks exceeding limits, summarize and ask to proceed with the next 200-line window or next file.
- If contradictions exist, propose the smallest doc/link edit to resolve and stop for confirmation.
