"""
MUTT Event Sender
==================

Purpose
 - Replay demo syslog events to rsyslog (UDP/514) and demo SNMP traps to snmptrapd (UDP/162)
 - Validate end-to-end forwarding paths into MUTT Ingestor via rsyslog+omhttp and snmptrapd→forwarder

Usage
 - Syslog (to local rsyslog UDP input):
     python mutt_event_sender.py syslog demo_syslog_events.json 127.0.0.1 \
       --rate 200 --facility local0 --syslog-port 514

 - SNMP traps (to local snmptrapd):
     python mutt_event_sender.py snmptrap demo_snmp_traps.json 127.0.0.1 \
       --rate 50 --community public --snmp-port 162

 - Dry run (print but don’t send):
     python mutt_event_sender.py syslog demo_syslog_events.json 127.0.0.1 --dry-run

Prerequisites
 - rsyslog listening on UDP 514 (enable imudp). Example config (RHEL/Ubuntu):
     module(load="imudp")
     input(type="imudp" port="514")
 - snmptrapd listening on UDP 162 for your community (e.g., "public"). Example:
     sudo snmptrapd -On -n -Lo -C -c /etc/snmp/snmptrapd.conf udp:162
 - Python dependencies: pip install -r requirements.txt (includes pysnmp)

Input File Schemas
 - demo_syslog_events.json: array of objects with fields:
     {"hostname": str, "timestamp": str, "message": str, "syslog_severity": str, "source_type": str}
 - demo_snmp_traps.json: array of objects with fields:
     {"source_ip": str, "timestamp": str, "trap_oid": str, "variables": ["@{oid=...; value=...}", ...], "severity": str}
   variables also accept [{'oid': '1.2.3', 'value': 'x'}] style

Notes
 - Syslog messages are formatted as RFC 5424 over UDP.
 - SNMP traps are sent as SNMPv2c and include snmpTrapOID.0 and provided varbinds.
 - Use --rate to control throughput (messages per second). The sender paces without significant drift.
 - This tool is for lab/demo use; extend as needed for TLS/TCP or SNMPv3.
"""

import argparse
import json
import socket
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

try:
    # pysnmp is optional; only required for --mode snmptrap
    from pysnmp.hlapi import (
        SnmpEngine,
        CommunityData,
        UdpTransportTarget,
        ContextData,
        NotificationType,
        ObjectIdentity,
        ObjectType,
        sendNotification,
    )
except Exception:
    SnmpEngine = None  # type: ignore

# [Claude: Write a detailed help message for the script, explaining the different modes and options.]
def get_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "MUTT Event Sender: replay syslog events to rsyslog (UDP/514) or SNMP traps to snmptrapd (UDP/162).\n"
            "Input file must be a JSON array of event objects.\n"
            "Use --rate to control messages per second."
        )
    )
    parser.add_argument("mode", choices=["syslog", "snmptrap"], help="Mode: send syslog or SNMP traps")
    parser.add_argument("file", help="Path to JSON file containing events")
    parser.add_argument("server", help="Target server hostname or IP")

    parser.add_argument("--rate", type=float, default=10.0, help="Messages per second (default: 10)")
    parser.add_argument("--syslog-port", type=int, default=514, help="Syslog UDP port (default: 514)")
    parser.add_argument("--snmp-port", type=int, default=162, help="SNMP trap UDP port (default: 162)")
    parser.add_argument("--community", default="public", help="SNMPv2c community (default: public)")
    parser.add_argument(
        "--facility",
        default="local0",
        help="Syslog facility (name or number). Default: local0",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print messages instead of sending")
    return parser.parse_args()

# [Codex: Implement the function to send a syslog message. It should take the server, port, and message as arguments.]
def _severity_to_code(sev: str) -> int:
    mapping = {
        "emergency": 0,
        "alert": 1,
        "critical": 2,
        "crit": 2,
        "error": 3,
        "err": 3,
        "warning": 4,
        "warn": 4,
        "notice": 5,
        "informational": 6,
        "info": 6,
        "debug": 7,
    }
    return mapping.get(str(sev).strip().lower(), 6)


def _facility_to_code(fac: str) -> int:
    if isinstance(fac, int):
        return fac
    names = {
        "kernel": 0,
        "user": 1,
        "mail": 2,
        "daemon": 3,
        "auth": 4,
        "syslog": 5,
        "lpr": 6,
        "news": 7,
        "uucp": 8,
        "cron": 9,
        "authpriv": 10,
        "ftp": 11,
        "ntp": 12,
        "security": 13,
        "console": 14,
        "clock": 15,
        "local0": 16,
        "local1": 17,
        "local2": 18,
        "local3": 19,
        "local4": 20,
        "local5": 21,
        "local6": 22,
        "local7": 23,
    }
    try:
        return int(fac)
    except Exception:
        return names.get(str(fac).strip().lower(), 16)


def send_syslog_message(
    server: str,
    port: int,
    message: str,
    hostname: str,
    severity: str,
    facility: str = "local0",
    app_name: str = "mutt-sender",
    msgid: str = "-",
    dry_run: bool = False,
) -> None:
    """Send a syslog message (RFC 5424) over UDP."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    sev_code = _severity_to_code(severity)
    fac_code = _facility_to_code(facility)
    pri = fac_code * 8 + sev_code
    # RFC 5424: <PRI>VERSION TIMESTAMP HOST APP PROCID MSGID STRUCTURED-DATA MSG
    syslog_msg = f"<{pri}>1 {ts} {hostname} {app_name} - {msgid} - {message}"

    if dry_run:
        print(f"[DRY-RUN] SYSLOG {server}:{port} <- {syslog_msg}")
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(syslog_msg.encode("utf-8", errors="replace"), (server, port))
    finally:
        sock.close()

# [Codex: Implement the function to send an SNMP trap. It should take the server, port, and trap data as arguments.]
def _parse_varbinds(vars_list: List[Any]) -> List[Tuple[str, Any]]:
    out: List[Tuple[str, Any]] = []
    for item in vars_list:
        if isinstance(item, dict) and "oid" in item and "value" in item:
            out.append((str(item["oid"]), item["value"]))
        elif isinstance(item, str):
            # support "@{oid=1.2.3; value=foo}" format from sample data
            s = item.strip()
            if s.startswith("@{") and s.endswith("}"):
                s = s[2:-1]
            parts = dict(
                kv.split("=", 1) for kv in [p.strip() for p in s.split(";") if "=" in p]
            )
            if "oid" in parts and "value" in parts:
                out.append((parts["oid"], parts["value"]))
        else:
            continue
    return out


def send_snmp_trap(
    server: str,
    port: int,
    trap_data: Dict[str, Any],
    community: str = "public",
    dry_run: bool = False,
) -> None:
    """Send an SNMPv2c trap using pysnmp."""
    trap_oid = str(trap_data.get("trap_oid", "1.3.6.1.6.3.1.1.5.1"))
    variables = trap_data.get("variables", [])
    var_binds = _parse_varbinds(variables)

    if dry_run:
        print(f"[DRY-RUN] SNMP {server}:{port} community={community} oid={trap_oid} vars={var_binds}")
        return

    if SnmpEngine is None:
        raise RuntimeError("pysnmp is not installed. Install with: pip install pysnmp")

    # Build varBinds list
    snmp_var_binds = [
        # Mandatory snmpTrapOID.0 for SNMPv2 traps
        ObjectType(ObjectIdentity("1.3.6.1.6.3.1.1.4.1.0"), ObjectIdentity(trap_oid)),
    ]
    for oid, value in var_binds:
        # Try casting integers; else treat as OctetString implicitly
        try:
            val = int(value)
        except Exception:
            val = str(value)
        snmp_var_binds.append(ObjectType(ObjectIdentity(oid), val))

    errorIndication = next(
        sendNotification(
            SnmpEngine(),
            CommunityData(community, mpModel=1),  # SNMPv2c
            UdpTransportTarget((server, port)),
            ContextData(),
            "trap",
            NotificationType(ObjectIdentity(trap_oid)).addVarBinds(*snmp_var_binds),
        )
    )
    if errorIndication:
        raise RuntimeError(f"SNMP send error: {errorIndication}")

def main():
    """Main function."""
    args = get_args()

    try:
        with open(args.file, "r", encoding="utf-8") as f:
            events = json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found: {args.file}")
        return
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from file: {args.file}")
        return

    # [Claude: Print a message to the user indicating that the script is starting and what it's doing.]
    print(f"Starting MUTT Event Sender in {args.mode} mode")
    print(
        f"Sending events from {args.file} to {args.server} at ~{args.rate}/sec"
    )

    if not isinstance(events, list):
        print("Error: JSON file must contain an array of events")
        return

    # Timing control
    interval = 1.0 / max(float(args.rate), 0.1)
    next_send = time.perf_counter()

    facility = args.facility

    count = 0
    for event in events:
        if args.mode == "syslog":
            hostname = event.get("hostname", socket.gethostname())
            message = event.get("message", "")
            severity = event.get("syslog_severity", "info")
            try:
                send_syslog_message(
                    args.server,
                    args.syslog_port,
                    message,
                    hostname,
                    severity,
                    facility=facility,
                    msgid=str(event.get("source_type", "-")),
                    dry_run=args.dry_run,
                )
            except Exception as e:
                print(f"Syslog send failed: {e}")
        elif args.mode == "snmptrap":
            try:
                send_snmp_trap(
                    args.server,
                    args.snmp_port,
                    event,
                    community=args.community,
                    dry_run=args.dry_run,
                )
            except Exception as e:
                print(f"SNMP send failed: {e}")
        count += 1

        # Simple pacing without accumulating drift significantly
        next_send += interval
        sleep_for = next_send - time.perf_counter()
        if sleep_for > 0:
            time.sleep(sleep_for)

    # [Claude: Print a message to the user indicating that all events have been sent.]
    print(f"Done. Sent {count} events.")

if __name__ == "__main__":
    main()
