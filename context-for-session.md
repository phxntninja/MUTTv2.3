You are taking over a production middleware platform called MUTT (Moog/Monitoring Universal-Translation-Toolkit). 

DOCUMENTATION:
- You have 8 markdown files (parts 1-8) that describe the architecture, configuration, and operations
- Read them in numerical order starting with part 1

CODEBASE:
- You have 4 Python services (v2.3/v2.4) that implement the platform
- All services use environment variables for config and HashiCorp Vault for secrets
- Key patterns: BRPOPLPUSH for reliability, Prometheus metrics, health checks, graceful shutdown

CURRENT STATE:
- Architecture is production-ready
- Critical security fix implemented (v2.4 session-based auth)
- Component #1 (Ingest Webhook) now exists
- Database schema and Vault setup documented
- Monitoring/alerting configured

YOUR TASK:
[Specify what you want the AI to do next: e.g., "Create Dockerfiles", "Add unit tests", "Implement feature X"]