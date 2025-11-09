# **MUTT**
## Multi-Use Telemetry Tool

**Project Kick-off**
v2.3

---

## The Problem

**Our current alerting system is unsupportable.**
* We are retiring an old system built on hundreds of individual Perl scripts.
* It's brittle, hard to debug, and difficult to change.

**Our new tool, NetIM, has an "alerting gap."**
* NetIM is great for **archiving** events.
* But its alerting logic is too simple: it only alerts on **severity levels** (e.g., "Critical").

---

## Why This Is a Stability Risk

This "severity-only" logic creates two major problems:

1.  **Alert Noise:** We get flooded with "Critical" alerts that are not actionable.
    * *Result: Teams waste time and develop alert fatigue.*

2.  **Missed Events:** We *miss* important, actionable events that are not "Critical."
    * *Result: We are blind to real issues until it's too late.*

**We are reacting to noise instead of signal.**

---

## The Solution: MUTT

**MUTT is an intelligent "sidecar" for NetIM.**

It doesn't *replace* NetIM. It makes it *better*.

1.  MUTT intercepts all messages.
2.  It uses an advanced rules engine to find the *actual* signal.
3.  It forwards **only actionable alerts** for paging/ticketing.
4.  It still sends **all messages** to NetIM for archival.

**For Directors: MUTT restores stability by filtering noise and finding the real, hidden risks.**

---

## How MUTT Works
### The Architecture

![MUTT Architecture Diagram](https://i.imgur.com/gA3qjF1.png)

---

## How MUTT Helps (The "What")

**For Product Owners: MUTT enhances your tools.**
* **Adds Intelligence to NetIM:** MUTT provides the advanced logic NetIM is missing, making your platform more powerful.
* **Enables Moogsoft:** It reliably feeds high-quality, de-duplicated alerts to AIOps.
* **Centralizes Logic:** One place to manage all alert rules, not hundreds of scripts.

**For Engineers: MUTT is built for supportability.**
* **Modern Stack:** A single, clean Python application.
* **Observable:** Full Prometheus metrics, health checks, and correlation IDs.
* **Resilient:** Crashes don't lose messages.
* **Managed by API:** All rules are in a database, managed by a UI.

---

## Key Features (The "How")

**For Engineers: This is not "AI code." This is robust, observable engineering.**

* ✅ **No Message Loss:** A crash-safe `BRPOPLPUSH` queue pattern means messages are never lost.
* ✅ **Full Observability:** Prometheus metrics and health checks on every single component.
* ✅ **Production-Grade:** Uses Vault for secrets, TLS everywhere, and connection pooling.
* ✅ **Scalable:** All services are stateless and can be scaled horizontally.
* ✅ **Intelligent:** Advanced rule matching, environment detection (Prod/Dev), and unhandled event aggregation.

---

## Project Status & Next Steps

* **Status:** Version 2.3 is production-ready.
* **Database:** Schema is defined.
* **Services:** All four microservices are coded and containerized.

**Next Steps:**
1.  Deploy to development environment.
2.  Begin integration testing with `rsyslog` and NetIM.
3.  Onboard initial rule sets.
4.  Begin parallel testing against the legacy system.