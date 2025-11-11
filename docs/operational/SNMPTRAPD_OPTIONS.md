SNMP Trap Forwarding Options
===========================

This guide shows two supported ways to forward SNMP traps to MUTT via the Ingestor service.

Option A: Log traps to syslog and forward via rsyslog (simplest)
- Configure snmptrapd to log traps to syslog.
- rsyslog already forwards syslog to MUTT using `omhttp` JSON template.

Example snmptrapd invocation (logs to syslog facility):
- Run via systemd override or service options with `-LS 6` (local syslog) or `-Ls 6` depending on distro.
- Example foreground for testing:
  - `sudo snmptrapd -On -n -LS 6 -C -c /etc/snmp/snmptrapd.conf udp:162`

Minimal `/etc/snmp/snmptrapd.conf` for SNMPv2c:
```
disableAuthorization no
authCommunity log,execute,net public
```

Option B: Direct HTTP forwarding using traphandle script
- Configure snmptrapd to execute a handler that POSTs traps to MUTT Ingestor.
- Use the provided script `scripts/snmptrap_to_mutt.sh`.

Steps:
1) Place API key and URL for MUTT Ingestor in environment (systemd recommended):
   - `MUTT_INGEST_URL` (e.g., `http://127.0.0.1:8080/ingest` or `https://ingestor.lab:8443/ingest`)
   - `MUTT_INGEST_API_KEY` (from Vault)
2) Configure `/etc/snmp/snmptrapd.conf`:
```
disableAuthorization no
authCommunity log,execute,net public
traphandle default /opt/mutt/scripts/snmptrap_to_mutt.sh
```
3) Restart snmptrapd.

Advanced: SNMPv3 acceptance
- Add an authPriv user and permit with `authUser` directive (user must exist in Net-SNMP USM database):
```
# Example: accept traps from user "snmpv3user" with authPriv
authUser log,execute,net authPriv snmpv3user
```
- Create the SNMPv3 USM user via Net-SNMP tooling (varies by distro). Refer to Net-SNMP docs for snmptrapd user creation.

Testing
- Send a demo trap with the provided sender:
  - `python mutt_event_sender.py snmptrap demo_snmp_traps.json 127.0.0.1 --rate 20`
- Or with net-snmp tools:
  - `snmptrap -v2c -c public 127.0.0.1:162 '' 1.3.6.1.6.3.1.1.5.3`

