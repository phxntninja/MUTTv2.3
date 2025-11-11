# MUTT v2.5 Quick Start Guide

Get MUTT up and running with Docker in under 5 minutes using the developer CLI.

---

## Prerequisites

- Docker 20.10+ and Docker Compose 1.29+ installed
- Python 3.8+ and `pip`
- 4GB RAM minimum

---

## 3-Step Quick Start

### Step 1: Set up the Environment

The `muttdev` CLI tool automates the setup process.

```bash
# Clone the repository
git clone https://github.com/yourusername/mutt.git
cd mutt

# Install dependencies and the muttdev CLI
pip install -r requirements.txt
pip install -e .

# Set up the development environment (creates .env, starts containers)
muttdev setup
```

This will start all the required services in Docker, including:
- Redis, PostgreSQL, Vault
- All MUTT services (Ingestor, Alerter, Moog Forwarder, Web UI)
- Mock Moog, Prometheus, and Grafana

### Step 2: Verify Health

Use the `muttdev` tool to check the health of all services.

```bash
# Check the health of all services
muttdev health
```

You should see a "healthy" status for all services.

### Step 3: Send a Test Message

Use the `muttdev` tool to send a test message.

```bash
# Send a test syslog message
muttdev send-event --type syslog --message "CRITICAL: Test alert from quickstart"
```

This will send a test event to the Ingestor service.

---

## Access Services

| Service | URL | Credentials |
|---|---|---|
| **Web UI** | http://localhost:8090 | API Key: `test-api-key-123` |
| **Prometheus** | http://localhost:9090 | None |
| **Grafana** | http://localhost:3000 | admin / admin |
| **Vault** | http://localhost:8200 | Token: `root-token-for-dev` |

---

## Common Operations with `muttdev`

### View Logs

```bash
# Stream logs for a specific service
muttdev logs --service ingestor --follow

# Tail the logs for all services
muttdev logs --tail 50
```

### Manage Services

```bash
# Stop all services
muttdev down

# Restart a specific service
muttdev restart alerter
```

### Run Tests

```bash
# Run all tests
muttdev test

# Run tests for a specific service
muttdev test --service ingestor
```

---

## Next Steps

For more advanced topics, see the following documents:

- **[README.md](README.md)**: For a general overview of the project.
- **[docs/CONFIGURATION.md](docs/CONFIGURATION.md)**: For detailed configuration of each service.
- **[docs/api/REFERENCE.md](docs/api/REFERENCE.md)**: For a detailed API reference.
- **[docs/architecture/DEPLOYMENT_ARCHITECTURE.md](docs/architecture/DEPLOYMENT_ARCHITECTURE.md)**: For detailed deployment instructions.

---

**🎉 You're now running MUTT v2.5!**