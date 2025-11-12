"""
muttdev status - Show status of all MUTT services
"""

import subprocess
import requests
from typing import Dict, Tuple


def register(subparsers):
    """Register the status command."""
    subparsers.add_parser(
        'status',
        help='Show status of all MUTT services',
        description='Check health and connectivity of MUTT services'
    )


def execute(args) -> int:
    """Execute the status command."""
    print("=" * 70)
    print("MUTT Service Status")
    print("=" * 70)
    print()

    services = {
        'Ingestor': 'http://localhost:8080/health',
        'Alerter': 'http://localhost:8082/health',
        'Moog Forwarder': 'http://localhost:8084/health',
        'Web UI': 'http://localhost:8090/health',
        'Remediation': 'http://localhost:8086/health',
        'Redis': 'localhost:6379',
        'PostgreSQL': 'localhost:5432'
    }

    all_healthy = True

    for name, endpoint in services.items():
        status, msg = check_service(name, endpoint)
        print(f"  {status} {name:20s} - {msg}")

        if '✗' in status:
            all_healthy = False

    print()
    print("=" * 70)

    if all_healthy:
        print("✓ All services healthy")
        return 0
    else:
        print("⚠ Some services are down")
        return 1


def check_service(name: str, endpoint: str) -> Tuple[str, str]:
    """Check if a service is healthy."""
    try:
        if endpoint.startswith('http'):
            # HTTP health check
            response = requests.get(endpoint, timeout=2)
            if response.status_code == 200:
                return "✓", "Healthy"
            else:
                return "✗", f"Unhealthy (HTTP {response.status_code})"
        elif ':' in endpoint:
            # TCP check for Redis/PostgreSQL
            host, port = endpoint.split(':')
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, int(port)))
            sock.close()

            if result == 0:
                return "✓", "Reachable"
            else:
                return "✗", "Not reachable"

    except Exception as e:
        return "✗", f"Error: {str(e)[:40]}"

    return "?", "Unknown"
