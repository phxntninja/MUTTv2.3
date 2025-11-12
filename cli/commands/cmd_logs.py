"""
muttdev logs - Stream and search service logs

This command helps developers view logs from MUTT services.
"""

import os
import sys
import subprocess
import re
from pathlib import Path


def register(subparsers):
    """Register the logs command with argparse."""
    parser = subparsers.add_parser(
        'logs',
        help='Stream and search service logs',
        description='View logs from MUTT services'
    )

    parser.add_argument(
        'service',
        nargs='?',
        choices=['ingestor', 'alerter', 'moog_forwarder', 'webui', 'remediation', 'all'],
        default='all',
        help='Service to view logs from (default: all)'
    )

    parser.add_argument(
        '-f', '--follow',
        action='store_true',
        help='Follow log output (like tail -f)'
    )

    parser.add_argument(
        '-n', '--lines',
        type=int,
        default=50,
        help='Number of lines to show (default: 50)'
    )

    parser.add_argument(
        '--grep',
        type=str,
        help='Filter logs by pattern (case-insensitive)'
    )

    parser.add_argument(
        '--level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Filter by log level'
    )

    parser.add_argument(
        '--json',
        action='store_true',
        help='Pretty-print JSON logs'
    )


def execute(args) -> int:
    """Execute the logs command."""
    # Check if docker-compose is being used
    if Path('docker-compose.yml').exists():
        return logs_docker(args)
    else:
        return logs_files(args)


def logs_docker(args) -> int:
    """View logs from docker-compose services."""
    cmd = ['docker-compose', 'logs']

    if args.follow:
        cmd.append('--follow')

    cmd.extend(['--tail', str(args.lines)])

    # Add service name if not 'all'
    if args.service and args.service != 'all':
        cmd.append(args.service)

    try:
        if args.grep or args.level or args.json:
            # Need to pipe through processing
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

            for line in process.stdout:
                # Apply filters
                if args.grep and not re.search(args.grep, line, re.IGNORECASE):
                    continue

                if args.level and args.level not in line:
                    continue

                # TODO: JSON pretty-printing
                print(line, end='')

            process.wait()
            return process.returncode

        else:
            # Just pass through directly
            subprocess.run(cmd)
            return 0

    except KeyboardInterrupt:
        print("\nLog streaming interrupted")
        return 0
    except Exception as e:
        print(f"Error viewing logs: {e}", file=sys.stderr)
        return 1


def logs_files(args) -> int:
    """View logs from log files."""
    log_dir = Path('/var/log/mutt')

    if not log_dir.exists():
        log_dir = Path.cwd() / 'logs'

    if not log_dir.exists():
        print("Error: Log directory not found")
        print(f"Searched: /var/log/mutt and {Path.cwd() / 'logs'}")
        return 1

    # Map service names to log files
    log_files = {
        'ingestor': log_dir / 'ingestor.log',
        'alerter': log_dir / 'alerter.log',
        'moog_forwarder': log_dir / 'moog_forwarder.log',
        'webui': log_dir / 'webui.log',
        'remediation': log_dir / 'remediation.log'
    }

    # Determine which files to tail
    if args.service == 'all':
        files = list(log_files.values())
    else:
        files = [log_files[args.service]]

    # Filter to existing files
    files = [f for f in files if f.exists()]

    if not files:
        print(f"Error: No log files found for service '{args.service}'")
        return 1

    # Build tail command
    cmd = ['tail']

    if args.follow:
        cmd.append('-f')

    cmd.extend(['-n', str(args.lines)])
    cmd.extend([str(f) for f in files])

    try:
        if args.grep or args.level:
            # Pipe through grep
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

            for line in process.stdout:
                if args.grep and not re.search(args.grep, line, re.IGNORECASE):
                    continue

                if args.level and args.level not in line:
                    continue

                print(line, end='')

            process.wait()
            return process.returncode

        else:
            subprocess.run(cmd)
            return 0

    except KeyboardInterrupt:
        print("\nLog streaming interrupted")
        return 0
    except Exception as e:
        print(f"Error viewing logs: {e}", file=sys.stderr)
        return 1
