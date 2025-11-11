# MUTT v2.5 - Operations Documentation

This directory contains all operational documentation for deploying, managing, and maintaining MUTT in production.

---

## 📋 Quick Access

### Priority 1 (Critical - Start Here)

1. **[Installation & Deployment Guide](INSTALLATION_GUIDE.md)** (25-30 pages)
   - Deploy MUTT on standalone RHEL servers
   - systemd service configuration
   - Firewall and SELinux setup

2. **[Service Operations Guide](SERVICE_OPERATIONS.md)** (22 pages)
   - Start/stop/restart services
   - Scaling procedures
   - Performance tuning

3. **[Comprehensive Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md)** (38 pages)
   - Systematic problem diagnosis
   - Service-by-service troubleshooting
   - Common error messages

### Priority 2 (Essential)

4. **[Configuration Management Guide](CONFIG_MANAGEMENT.md)** (18-20 pages)
   - Static/dynamic configuration
   - Vault secrets management
   - Configuration backup/restore

5. **[Monitoring & Alerting Setup Guide](MONITORING_ALERTING.md)** (24-25 pages)
   - Prometheus/Alertmanager/Grafana setup
   - Alert rules and notifications
   - SLO monitoring

6. **[Backup & Recovery Guide](BACKUP_RECOVERY.md)** (16-17 pages)
   - Automated backup procedures
   - Disaster recovery scenarios
   - Full system restoration

7. **[Incident Response Runbook](INCIDENT_RESPONSE.md)** (14-15 pages)
   - On-call procedures
   - Incident classification
   - Post-incident reviews

---

## 🎯 Documentation by Task

### I Need to Deploy MUTT
→ [Installation Guide](INSTALLATION_GUIDE.md)

### I Need to Configure MUTT
→ [Configuration Management](CONFIG_MANAGEMENT.md)

### I Need to Monitor MUTT
→ [Monitoring & Alerting Setup](MONITORING_ALERTING.md)

### I Need to Troubleshoot Issues
→ [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md)

### I Need to Scale MUTT
→ [Service Operations](SERVICE_OPERATIONS.md) - Scaling section

### I Need to Back Up MUTT
→ [Backup & Recovery](BACKUP_RECOVERY.md)

### I'm On-Call and There's an Incident
→ [Incident Response Runbook](INCIDENT_RESPONSE.md)

---

## 📊 Documentation Coverage

**Total:** ~170 pages of operational documentation

- ✅ Installation and deployment
- ✅ Service management and operations
- ✅ Configuration management (static + dynamic + secrets)
- ✅ Monitoring and alerting setup
- ✅ Troubleshooting (systematic approach)
- ✅ Backup and disaster recovery
- ✅ Incident response procedures

---

## 🗂️ Files in This Directory

```
docs/operations/
├── README.md                    # This file
├── DOCUMENTATION_PLAN.md        # Master plan for all operational docs
├── INSTALLATION_GUIDE.md        # P1: Complete deployment guide
├── SERVICE_OPERATIONS.md        # P1: Service management
├── TROUBLESHOOTING_GUIDE.md     # P1: Problem diagnosis
├── CONFIG_MANAGEMENT.md         # P2: Configuration guide
├── MONITORING_ALERTING.md       # P2: Monitoring setup
├── BACKUP_RECOVERY.md           # P2: Disaster recovery
└── INCIDENT_RESPONSE.md         # P2: Incident procedures
```

---

## 📖 Related Documentation

- **Architecture**: [../architecture/](../architecture/) - System architecture, design rationale
- **API Docs**: [../api/](../api/) - REST API reference
- **Developer Docs**: [../DEV_QUICKSTART.md](../DEV_QUICKSTART.md) - Local development setup
- **ADRs**: [../adr/](../adr/) - Architecture Decision Records
- **Main Index**: [../INDEX.md](../INDEX.md) - Complete documentation index

---

## 🚀 Getting Started

**If you're deploying MUTT for the first time:**

1. Read the [Documentation Plan](DOCUMENTATION_PLAN.md) to understand scope
2. Follow the [Installation Guide](INSTALLATION_GUIDE.md) step-by-step
3. Set up monitoring using the [Monitoring & Alerting Setup](MONITORING_ALERTING.md)
4. Configure backups using the [Backup & Recovery Guide](BACKUP_RECOVERY.md)
5. Familiarize yourself with the [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md)
6. Review the [Incident Response Runbook](INCIDENT_RESPONSE.md) for on-call

**Estimated time to full production deployment:** 4-8 hours

---

## 🆘 Emergency Quick Links

**Production Incident?**
→ [Incident Response Runbook](INCIDENT_RESPONSE.md)

**Service Down?**
→ [Troubleshooting Guide - Service Down](TROUBLESHOOTING_GUIDE.md#service-specific-troubleshooting)

**Need to Restart Services?**
→ [Service Operations - Starting and Stopping](SERVICE_OPERATIONS.md#starting-and-stopping-services)

**Configuration Issue?**
→ [Troubleshooting - Configuration](TROUBLESHOOTING_GUIDE.md#configuration-validation)

---

**Version:** 2.5
**Last Updated:** 2025-11-10
**Maintained By:** MUTT Operations Team
