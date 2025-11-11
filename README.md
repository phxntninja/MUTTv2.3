# MUTT - Multi-Use Telemetry Tool

[![Version](https://img.shields.io/badge/version-2.5-blue.svg)](docs/CHANGELOG.md)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

**MUTT** (Multi-Use Telemetry Tool) is a production-ready, horizontally scalable event processing system for
syslog and SNMP trap ingestion, intelligent alert routing, and integration with enterprise monitoring platforms
like Moogsoft.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Key Features](#key-features)
- [Components](#components)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Deployment](#deployment)
- [Monitoring](#monitoring)
- [Development](#development)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## 🎯 Overview

MUTT provides a robust, fault-tolerant pipeline for processing network events from syslog and SNMP traps. It
intelligently routes events based on configurable rules, distinguishes between production and development
environments, and forwards alerts to downstream systems like Moogsoft.

### v2.5 Highlights
- **Dynamic Config**: Redis-backed runtime tuning with Pub/Sub invalidation
- **Observability**: Structured logging, metrics, tracing, SLO endpoint and rules
- **Reliability**: Backpressure controls, remediation service, circuit breaker patterns
- **Compliance**: Audit logging, API versioning, retention automation and docs
- **DevEx**: `muttdev` CLI, ADRs, CI across OS/Python, quickstart docs

---

## 🏗️ Architecture

For a detailed architecture overview, see the [Architecture Documentation](docs/architecture/SYSTEM_ARCHITECTURE.md).

---

## ✨ Key Features

For a detailed feature matrix, see the [Feature Matrix](docs/FEATURE_MATRIX.md).

---

## 🧩 Components

MUTT is composed of four main services:

1.  **Ingestor Service**: Receives events from monitoring sources.
2.  **Alerter Service**: Processes events based on user-defined rules.
3.  **Moog Forwarder Service**: Forwards alerts to Moogsoft.
4.  **Web UI Service**: Provides a web interface for managing the system.

For more details on each component, see the [Components Overview](docs/code/MODULES.md).

---

## 📦 Requirements

- **Python**: 3.8+
- **Redis**: 6.0+
- **PostgreSQL**: 12+
- **HashiCorp Vault**: 1.8+

For a complete list of dependencies, see the `requirements.txt` file.

---

## 🚀 Quick Start

See the [QUICKSTART.md](QUICKSTART.md) for a guide to getting MUTT up and running with Docker Compose in under 10 minutes.

---

## ⚙️ Configuration

For detailed configuration of each service, see the [CONFIGURATION.md](docs/CONFIGURATION.md) document.

---

## 📡 API Reference

For a detailed API reference, see the [API_REFERENCE.md](docs/api/REFERENCE.md) document.

---

## 🐳 Deployment

For detailed deployment instructions, see the [DEPLOYMENT_ARCHITECTURE.md](docs/architecture/DEPLOYMENT_ARCHITECTURE.md) document.

---

## 📊 Monitoring

For detailed information on monitoring and available metrics, see the [observability.md](docs/observability.md) document.

---

## 🛠️ Development

For development standards and guidelines, see the [DEVELOPMENT_STANDARDS.md](docs/DEVELOPMENT_STANDARDS.md) document.

---

## 🧪 Testing

For information on running the test suite, see the [tests/README_TESTS.md](tests/README_TESTS.md) document.

---

## 🔧 Troubleshooting

For common issues and solutions, see the [TROUBLESHOOTING_GUIDE.md](docs/operations/TROUBLESHOOTING_GUIDE.md) document.

---

## 🤝 Contributing

Contributions are welcome! Please see the [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

Built with ❤️ by the MUTT Team | Version 2.5