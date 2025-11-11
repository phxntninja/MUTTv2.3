Presentation & Delivery Guide - MUTT v2.5

Purpose
- Provide clear, practical steps to view and present the MUTT documentation and slides, and tactics to ensure the presentation lands well with both product owners and technical leaders.

Where To Start
- Master Index: docs/INDEX.md
- Executive/Technical Overview (Markdown): docs/summary/MUTT_OVERVIEW.md
- One-pager (landscape, 16:9): docs/slides/ONE_PAGER.html
- Executive deck (Reveal.js): docs/slides/mutt_v25_exec.html
- Technical deck (Reveal.js): docs/slides/mutt_v25_tech.html
- Diagram (SVG): docs/images/mutt-overview.svg
- Diagram (export to PNG): docs/images/mutt-overview.png (generate via scripts below)

Viewing The Docs
- Open docs/INDEX.md for navigation to all content.
- API Reference: docs/api/REFERENCE.md; OpenAPI at docs/api/openapi.yaml and ReDoc at docs/api/redoc.html.
- Code Modules: docs/code/MODULES.md; DB Schema: docs/db/SCHEMA.md.

Viewing The Slides
- One-pager (no internet required):
  - Open docs/slides/ONE_PAGER.html in a browser (Chrome/Edge recommended).
  - Adjust zoom (90-110%) to fit the projector or screen.
- Executive and Technical Reveal.js decks:
  - Open docs/slides/mutt_v25_exec.html or docs/slides/mutt_v25_tech.html in a browser.
  - These files load Reveal.js from a CDN (internet required). For offline use, see Offline Mode below.
  - Navigation: arrow keys; URL hash updates per slide; use F for fullscreen.

Export Diagram To PNG (for decks or handouts)
- Linux/macOS: bash scripts/export_diagrams.sh
- Windows PowerShell: ./scripts/export_diagrams.ps1
- Requirements: Inkscape or rsvg-convert installed. Output is docs/images/mutt-overview.png (default width 1920px).

Offline Mode (optional)
- Vendor local assets for Reveal.js once, then use the offline decks:
  - Windows: ./scripts/vendor_reveal.ps1
  - Linux/macOS: bash scripts/vendor_reveal.sh
  - Result: assets under docs/slides/vendor/reveal/dist
- Use offline decks (no internet required):
  - docs/slides/mutt_v25_exec_offline.html
  - docs/slides/mutt_v25_tech_offline.html
- If a browser blocks file:// loads, serve locally:
  - Python: python -m http.server 8089, then open http://localhost:8089/docs/slides/...
  - Node: npx http-server docs -p 8089

Suggested Agenda (20-30 min)
- Opening (2-3 min): Why MUTT now? Problem + noise, slow MTTR, reliability risk.
- Executive overview (5-7 min): Benefits, outcomes, scope, what's new in v2.5 (use the one-pager).
- Technical overview (8-12 min): Flow with ports, resilience (backpressure, BRPOPLPUSH, circuit breaker), auditability (use diagram + tech deck).
- (Optional) Quick demo (3-5 min): Health checks + sample ingest call + Web UI rules list.
- Close (2-3 min): Rollout path, support model, success measures; Q&A.

Demo Flow (Scripted, Fast)
- Health endpoints:
  - Ingestor: curl -f http://localhost:8080/health
  - Forwarder: curl -f http://localhost:8084/health
  - Web UI: curl -f http://localhost:8090/health
- Post a sample event:
  - curl -s -X POST http://localhost:8080/api/v2/ingest -H "Content-Type: application/json" -H "X-API-KEY: <INGEST_API_KEY>" -d '{"timestamp":"2025-11-10T12:00:00Z","message":"hello","hostname":"demo","syslog_severity":4}'
- Show Web UI API (rules):
  - curl -s -H "X-API-KEY: <WEBUI_API_KEY>" http://localhost:8090/api/v2/rules | jq '.rules | length'

Audience Framing
- Product Owners / Execs:
  - Emphasize business impact: lower MTTR, fewer false pages, controlled egress risk, audit trail for compliance, safer deployments via versioned APIs.
  - Keep jargon light; quantify with examples (e.g., % reduction in noisy alerts).
- Technical Leaders / Engineers:
  - Emphasize operational safety and maintainability: queue caps, BRPOPLPUSH + janitor, rate limiting + circuit breaker, DLQ.
  - Highlight predictable interfaces: version headers, OpenAPI spec, metrics catalog, SLOs.

Delivery Tips (To Be Well Received)
- Visual clarity: large fonts, high contrast, minimal text per slide. The one-pager is 16:9 and legible on projectors.
- Tell a story: Problem + Solution + Impact + Proof (metrics/tests) + Next steps.
- Time box sections; leave room for Q&A (5 min). Seed questions around rollout and integration.
- De-risk the live portion: pre-run docker-compose.test.yml or a local RHEL instance; cache dependencies.
- Always have a fallback: print the one-pager to PDF and the diagram to PNG; keep commands ready in a notes doc.
- Sanitize secrets/API keys in any demos; use test keys.

Contingency Plan
- No internet: use the one-pager and PNG diagram; run decks via local server or offline-vendored assets.
- Projector scaling: change browser zoom (90-125%); test 10 minutes before.
- Demo failure: show logs/health endpoints and recorded outputs; pivot to architecture Q&A.

Follow-Up Material
- docs/summary/MUTT_OVERVIEW.md - leave-behind summary (executive + technical)
- docs/api/openapi.yaml - integration reference
- docs/prometheus/alerts-v25.yml - operations reference

Contacts & Next Steps
- Propose a pilot (limited scope) with success metrics (alert noise reduction %, MTTR change, false positive rate).
- Offer a short technical workshop for integrating with existing rsyslog/snmptrapd setups.

