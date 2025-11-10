#!/usr/bin/env python3
"""
MUTT v2.5 – Developer CLI (muttdev)

Lightweight helper for common developer tasks.

Commands
- setup   : Create a local .env from template (no overwrite by default)
- config  : Show key configuration (db, redis, retention)
- logs    : Print suggested log/compose commands for a service

Usage
  python scripts/muttdev.py setup [--force]
  python scripts/muttdev.py config [--section all|db|redis|retention]
  python scripts/muttdev.py logs --service ingestor|alerter|forwarder|webui|remediation [--tail 200]
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

# Make local packages importable when run as a script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'config'))

try:
    from environment import (
        get_database_config,
        get_redis_config,
        get_retention_config,
    )
except Exception:
    # Fallbacks if config is unavailable
    def get_database_config():
        return {}

    def get_redis_config():
        return {}

    def get_retention_config():
        return {}


def cmd_setup(force: bool = False) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    env_template = repo_root / '.env.template'
    env_file = repo_root / '.env'

    if not env_template.exists():
        print(".env.template not found. Nothing to do.")
        return 1

    if env_file.exists() and not force:
        print(".env already exists. Use --force to overwrite.")
        return 0

    shutil.copyfile(env_template, env_file)
    print(f"Created {env_file.name} from template. Review values before running services.")
    return 0


def _print_section_header(title: str) -> None:
    print("\n" + title)
    print("-" * len(title))


def cmd_config(section: str = 'all') -> int:
    section = section.lower()
    show_all = section == 'all'

    if show_all or section == 'db':
        _print_section_header('Database')
        db = get_database_config()
        for k, v in db.items():
            if k == 'password' and v:
                v = '***'
            print(f"{k}: {v}")

    if show_all or section == 'redis':
        _print_section_header('Redis')
        rc = get_redis_config()
        pw = rc.get('password')
        if pw:
            rc['password'] = '***'
        for k, v in rc.items():
            print(f"{k}: {v}")

    if show_all or section == 'retention':
        _print_section_header('Retention')
        rt = get_retention_config()
        for k, v in rt.items():
            print(f"{k}: {v}")

    print("\nTip: set/override values in your environment or .env file.")
    return 0


def cmd_logs(service: str, tail: int) -> int:
    service = service.lower()
    compose_map = {
        'ingestor': 'ingestor',
        'alerter': 'alerter',
        'forwarder': 'moog-forwarder',
        'webui': 'webui',
        'remediation': 'remediation',
    }
    if service not in compose_map:
        print(f"Unknown service '{service}'. Choose from: {', '.join(compose_map.keys())}")
        return 1

    repo_root = Path(__file__).resolve().parent.parent
    compose_file = repo_root / 'docker-compose.yml'

    print("Suggested commands (copy-paste as needed):\n")
    if compose_file.exists():
        print(f"# Docker Compose logs (if using compose)\n"
              f"docker-compose logs -f --tail={tail} {compose_map[service]}\n")

    # Generic paths that some deployments use
    log_paths = {
        'ingestor': ['/var/log/mutt/ingestor.log'],
        'alerter': ['/var/log/mutt/alerter.log'],
        'forwarder': ['/var/log/mutt/moog_forwarder.log'],
        'webui': ['/var/log/mutt/web_ui.log'],
        'remediation': ['/var/log/mutt/remediation.log'],
    }
    print("# System logs (if running via systemd or direct)\n"
          f"tail -n {tail} -F {' '.join(log_paths.get(service, []))}\n")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog='muttdev', description='MUTT Developer CLI')
    sub = parser.add_subparsers(dest='command', required=True)

    p_setup = sub.add_parser('setup', help='Create a local .env from template')
    p_setup.add_argument('--force', action='store_true', help='Overwrite existing .env')

    p_cfg = sub.add_parser('config', help='Show key configuration values')
    p_cfg.add_argument('--section', choices=['all', 'db', 'redis', 'retention'], default='all')

    p_logs = sub.add_parser('logs', help='Print suggested log commands for a service')
    p_logs.add_argument('--service', required=True,
                        choices=['ingestor', 'alerter', 'forwarder', 'webui', 'remediation'])
    p_logs.add_argument('--tail', type=int, default=200)

    args = parser.parse_args(argv)

    if args.command == 'setup':
        return cmd_setup(force=args.force)
    if args.command == 'config':
        return cmd_config(section=args.section)
    if args.command == 'logs':
        return cmd_logs(service=args.service, tail=args.tail)

    parser.print_help()
    return 1


if __name__ == '__main__':
    sys.exit(main())

