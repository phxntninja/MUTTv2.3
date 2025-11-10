#!/usr/bin/env python3
"""
MUTT v2.5 – Developer CLI (muttdev)

Lightweight helper for common developer tasks.

Commands
- setup   : Create a local .env from template (no overwrite by default)
- config  : Show key configuration (db, redis, retention)
- logs    : Print suggested log/compose commands for a service
- up      : Bring up services via docker-compose (optional service filter)
- test    : Run tests (quick subset or full)
- down    : Stop services via docker-compose
- doctor  : Environment checks (tools, imports, basic connectivity)

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
import subprocess
from typing import List, Optional

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


def _run(cmd: List[str], cwd: Optional[Path] = None) -> int:
    try:
        print("$", " ".join(cmd))
        proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None)
        return proc.returncode
    except FileNotFoundError:
        print(f"Command not found: {cmd[0]}")
        return 127


def cmd_up(services: List[str]) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    compose_file = repo_root / 'docker-compose.yml'
    if not compose_file.exists():
        print("docker-compose.yml not found at repo root.")
        return 1
    cmd = ['docker-compose', 'up', '-d'] + services
    return _run(cmd, cwd=repo_root)


def cmd_test(quick: bool, kexpr: Optional[str], path: Optional[str]) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    # Prefer invoking pytest via the current Python interpreter to avoid PATH issues
    pytest_cmd = [sys.executable, '-m', 'pytest', '-q']
    # Check pytest availability and emit guidance if missing
    try:
        import pytest as _pytest  # noqa: F401
    except Exception:
        print("pytest is not installed for this Python interpreter.")
        print("Install deps, then rerun:")
        print("  python -m pip install -r requirements.txt -r tests/requirements-test.txt")
        print("  python scripts/muttdev.py test --quick")
        return 127
    if quick:
        # Target high-signal Phase 4/3 areas by default
        targets = [
            'tests/test_retention_cleanup.py',
            'tests/test_retention_integration.py',
            'tests/test_api_versioning.py',
            'tests/test_versioning_integration.py',
        ]
        cmd = pytest_cmd + targets
    else:
        cmd = pytest_cmd + ([path] if path else [])
    if kexpr:
        cmd += ['-k', kexpr]
    return _run(cmd, cwd=repo_root)


def cmd_down(services: List[str]) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    compose_file = repo_root / 'docker-compose.yml'
    if not compose_file.exists():
        print("docker-compose.yml not found at repo root.")
        return 1
    cmd = ['docker-compose', 'down'] if not services else ['docker-compose', 'stop'] + services
    return _run(cmd, cwd=repo_root)


def cmd_doctor() -> int:
    import shutil as _shutil
    issues = 0
    def ok(msg: str):
        print(f"[OK] {msg}")
    def warn(msg: str):
        nonlocal issues
        issues += 1
        print(f"[WARN] {msg}")

    # Python
    pyver = sys.version.split()[0]
    ok(f"Python {pyver}")

    # Tooling
    for tool in [
        ('docker', 'Docker engine (optional for compose)'),
        ('docker-compose', 'Docker Compose (optional)'),
        ('redis-cli', 'Redis CLI (optional)'),
        ('psql', 'PostgreSQL client (optional)'),
    ]:
        name, desc = tool
        if _shutil.which(name):
            ok(f"{name}: found ({desc})")
        else:
            warn(f"{name}: not found ({desc})")

    # Imports
    try:
        import psycopg2  # noqa: F401
        ok("psycopg2 import ok")
    except Exception as e:
        warn(f"psycopg2 import failed: {e}")
    try:
        import redis as _redis  # noqa: F401
        ok("redis import ok")
    except Exception as e:
        warn(f"redis import failed: {e}")
    try:
        import pytest  # noqa: F401
        ok("pytest import ok")
    except Exception as e:
        warn(f"pytest import failed: {e}")

    # Config + basic connectivity
    try:
        db = get_database_config()
        if db:
            import psycopg2
            try:
                conn = psycopg2.connect(
                    host=db.get('host'), port=db.get('port'),
                    database=db.get('database'), user=db.get('user'), password=db.get('password'),
                    connect_timeout=2
                )
                conn.close()
                ok("PostgreSQL connect OK (2s timeout)")
            except Exception as e:
                warn(f"PostgreSQL connect failed (2s timeout): {e}")
    except Exception as e:
        warn(f"Database config unavailable: {e}")

    try:
        rc = get_redis_config()
        if rc:
            import redis as _redis
            try:
                r = _redis.Redis(host=rc.get('host','localhost'), port=rc.get('port',6379), db=rc.get('db',0), password=rc.get('password',None), socket_timeout=1)
                r.ping()
                ok("Redis ping OK (1s timeout)")
            except Exception as e:
                warn(f"Redis ping failed (1s timeout): {e}")
    except Exception as e:
        warn(f"Redis config unavailable: {e}")

    if issues:
        print(f"\nDoctor finished with {issues} warning(s). Review above notes.")
        return 0
    print("\nDoctor checks passed.")
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

    p_up = sub.add_parser('up', help='Bring up services via docker-compose')
    p_up.add_argument('services', nargs='*', help='Optional list of services to start')

    p_test = sub.add_parser('test', help='Run tests (quick subset or full)')
    p_test.add_argument('--quick', action='store_true', help='Run a targeted subset of tests')
    p_test.add_argument('-k', dest='kexpr', help='Pytest -k expression')
    p_test.add_argument('path', nargs='?', help='Optional path to test file/dir')

    p_down = sub.add_parser('down', help='Stop services via docker-compose or stop specific services')
    p_down.add_argument('services', nargs='*', help='Optional list of services to stop (uses compose stop). No args uses compose down')

    sub.add_parser('doctor', help='Check tools, imports, and basic connectivity')

    args = parser.parse_args(argv)

    if args.command == 'setup':
        return cmd_setup(force=args.force)
    if args.command == 'config':
        return cmd_config(section=args.section)
    if args.command == 'logs':
        return cmd_logs(service=args.service, tail=args.tail)
    if args.command == 'up':
        return cmd_up(services=args.services)
    if args.command == 'test':
        return cmd_test(quick=args.quick, kexpr=args.kexpr, path=args.path)
    if args.command == 'down':
        return cmd_down(services=args.services)
    if args.command == 'doctor':
        return cmd_doctor()

    parser.print_help()
    return 1


if __name__ == '__main__':
    sys.exit(main())
