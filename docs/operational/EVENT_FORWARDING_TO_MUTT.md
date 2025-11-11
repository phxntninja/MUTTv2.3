Event Forwarding to MUTT
=======================

This reference collects deployment options and example configs to forward syslog and SNMP traps to the MUTT Ingestor.

Syslog ingestion via rsyslog
- UDP input: `docs/operational/RSYSLOG_UDP_INPUT.conf`
- TCP input: `docs/operational/RSYSLOG_TCP_INPUT.conf`
- Forward to MUTT over HTTP (TLS): `docs/operational/RSYSLOG_FORWARD_TO_MUTT_TLS.conf`

Quick steps (Ubuntu/RHEL):
- Place the desired input conf in `/etc/rsyslog.d/` and the forwarder conf (HTTP) as well.
- Replace `REPLACE_WITH_INGESTOR_API_KEY` and set `server`, `port`, and `tls.cacert` as needed.
- Restart rsyslog: `sudo systemctl restart rsyslog`.

SNMP traps via snmptrapd
- Options and examples: `docs/operational/SNMPTRAPD_OPTIONS.md`
  - Option A: Log traps to syslog; rsyslog forwards to MUTT.
  - Option B: Direct HTTP POST to MUTT using traphandle script.

Testing tools
- Use `mutt_event_sender.py` to replay demo data:
  - Syslog: `python mutt_event_sender.py syslog demo_syslog_events.json 127.0.0.1 --rate 200`
  - SNMP: `python mutt_event_sender.py snmptrap demo_snmp_traps.json 127.0.0.1 --rate 50`

Firewall reminders
- Allow UDP/TCP 514 for syslog inputs as configured.
- Allow UDP 162 for SNMP traps if using a remote sender.

