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
- fmt     : Format code with Black
- lint    : Lint with Ruff
- type    : Type-check with MyPy

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


def cmd_config(
    section: str = 'all',
    get_key: Optional[str] = None,
    set_kv: Optional[List[str]] = None,
    publish: bool = False,
    list_keys: bool = False,
) -> int:
    # Redis-backed get/set/list operations
    if get_key or set_kv or list_keys:
        try:
            import redis  # type: ignore
        except Exception as e:
            print(f"redis package not installed: {e}")
            return 127

        try:
            rc = get_redis_config()
            client = redis.Redis(
                host=rc.get('host', 'localhost'),
                port=rc.get('port', 6379),
                db=rc.get('db', 0),
                password=rc.get('password', None),
                socket_timeout=2,
            )
        except Exception as e:
            print(f"Failed to initialize Redis client: {e}")
            return 1

        prefix = 'mutt:config:'
        updates_channel = prefix + 'updates'

        if list_keys:
            try:
                count = 0
                for rkey in client.scan_iter(prefix + '*'):
                    key = rkey.decode('utf-8').split(':', 2)[-1]
                    if key == 'updates':
                        continue
                    val = client.get(rkey)
                    if isinstance(val, bytes):
                        val = val.decode('utf-8')
                    print(f"{key}={val}")
                    count += 1
                if count == 0:
                    print("No dynamic config keys found.")
                return 0
            except Exception as e:
                print(f"Failed to list keys: {e}")
                return 1

        if get_key:
            try:
                rkey = prefix + get_key
                val = client.get(rkey)
                if val is None:
                    print("<null>")
                else:
                    if isinstance(val, bytes):
                        val = val.decode('utf-8')
                    print(val)
                return 0
            except Exception as e:
                print(f"Failed to get key '{get_key}': {e}")
                return 1

        if set_kv:
            key, value = set_kv
            try:
                rkey = prefix + key
                client.set(rkey, str(value))
                if publish:
                    client.publish(updates_channel, key)
                print(f"Set {key}={value}{' (published)' if publish else ''}")
                return 0
            except Exception as e:
                print(f"Failed to set key '{key}': {e}")
                return 1

        return 0

    # Default: print config sections
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


def cmd_logs(service: str, tail: int, follow: bool) -> int:
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

    if follow:
        # Try docker-compose follow if available
        exe = shutil.which('docker-compose') or shutil.which('docker')
        if exe and compose_file.exists():
            if exe.endswith('docker'):
                cmd = [exe, 'compose', 'logs', '-f', f'--tail={tail}', compose_map[service]]
            else:
                cmd = [exe, 'logs', '-f', f'--tail={tail}', compose_map[service]]
            return _run(cmd, cwd=repo_root)
        print("Cannot follow logs automatically (docker-compose not found). Use the printed commands.")
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
        # Fast unit suites only (exclude slower integration tests by default)
        targets = [
            'tests/test_retention_cleanup.py',
            'tests/test_api_versioning.py',
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


def cmd_retention(dry_run: bool) -> int:
    """Run retention cleanup locally (optionally DRY RUN)."""
    repo_root = Path(__file__).resolve().parent.parent
    script = repo_root / 'scripts' / 'retention_cleanup.py'
    env = os.environ.copy()
    if dry_run:
        env['RETENTION_DRY_RUN'] = 'true'
    # Use the current Python interpreter
    try:
        print("$", sys.executable, str(script))
        proc = subprocess.run([sys.executable, str(script)], cwd=str(repo_root), env=env)
        return proc.returncode
    except FileNotFoundError:
        print("Python interpreter not found to run retention script.")
        return 127


def cmd_e2e() -> int:
    """Run docker-compose E2E smoke test via scripts/run_e2e.sh."""
    repo_root = Path(__file__).resolve().parent.parent
    runner = repo_root / 'scripts' / 'run_e2e.sh'
    if not runner.exists():
        print("scripts/run_e2e.sh not found.")
        return 1
    return _run(['bash', str(runner)], cwd=repo_root)


def cmd_load(url: str, api_key: str, count: int, threads: int, timeout: float) -> int:
    """Run ingest load test script with provided parameters."""
    repo_root = Path(__file__).resolve().parent.parent
    script = repo_root / 'tests' / 'load' / 'flood_ingest.py'
    args = [
        sys.executable, str(script),
        '--url', url,
        '--api-key', api_key,
        '--count', str(count),
        '--threads', str(threads),
        '--timeout', str(timeout),
    ]
    return _run(args, cwd=repo_root)


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

    for mod, label in [("black", "black"), ("ruff", "ruff"), ("mypy", "mypy")]:
        try:
            __import__(mod)
            ok(f"{label} import ok")
        except Exception as e:
            warn(f"{label} import failed: {e}")

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
                r = _redis.Redis(
                    host=rc.get('host', 'localhost'),
                    port=rc.get('port', 6379),
                    db=rc.get('db', 0),
                    password=rc.get('password', None),
                    socket_timeout=1,
                )
                r.ping()
                ok("Redis ping OK (1s timeout)")
                # Quick dynamic config check (non-fatal)
                try:
                    count = 0
                    for _ in r.scan_iter('mutt:config:*'):
                        count += 1
                        if count >= 1:
                            break
                    if count > 0:
                        ok("DynamicConfig prefix present (mutt:config:*)")
                    else:
                        warn("DynamicConfig keys not found (mutt:config:*). Use 'muttdev config --list' to verify or initialize.")
                except Exception as e:
                    warn(f"DynamicConfig key scan failed: {e}")
            except Exception as e:
                warn(f"Redis ping failed (1s timeout): {e}")
    except Exception as e:
        warn(f"Redis config unavailable: {e}")

    if issues:
        print(f"\nDoctor finished with {issues} warning(s). Review above notes.")
        return 0
    print("\nDoctor checks passed.")
    return 0


def cmd_fmt(paths: List[str]) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    targets = paths or ["services", "scripts", "tests", "docs", "*.py"]
    cmd = [sys.executable, "-m", "black", "-l", "100"] + targets
    return _run(cmd, cwd=repo_root)


def cmd_lint(paths: List[str]) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    targets = paths or ["services", "scripts", "tests"]
    cmd = [sys.executable, "-m", "ruff", "check"] + targets
    return _run(cmd, cwd=repo_root)


def cmd_type(paths: List[str]) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    targets = paths or ["services"]
    cmd = [sys.executable, "-m", "mypy"] + targets
    return _run(cmd, cwd=repo_root)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog='muttdev', description='MUTT Developer CLI')
    sub = parser.add_subparsers(dest='command', required=True)

    p_setup = sub.add_parser('setup', help='Create a local .env from template')
    p_setup.add_argument('--force', action='store_true', help='Overwrite existing .env')

    p_cfg = sub.add_parser('config', help='Show key configuration values or manage dynamic config')
    p_cfg.add_argument('--section', choices=['all', 'db', 'redis', 'retention'], default='all', help='Print configuration sections (default: all)')
    p_cfg.add_argument('--get', dest='get_key', help='Get dynamic config key (Redis)')
    p_cfg.add_argument('--set', dest='set_kv', nargs=2, metavar=('KEY', 'VALUE'), help='Set dynamic config key (Redis)')
    p_cfg.add_argument('--publish', action='store_true', help='Publish change notification on set')
    p_cfg.add_argument('--list', dest='list_keys', action='store_true', help='List all dynamic config keys from Redis')

    p_logs = sub.add_parser('logs', help='Print suggested log commands for a service')
    p_logs.add_argument('--service', required=True,
                        choices=['ingestor', 'alerter', 'forwarder', 'webui', 'remediation'])
    p_logs.add_argument('--tail', type=int, default=200)
    p_logs.add_argument('--follow', action='store_true', help='Follow logs via docker-compose if available')

    p_up = sub.add_parser('up', help='Bring up services via docker-compose')
    p_up.add_argument('services', nargs='*', help='Optional list of services to start')

    p_test = sub.add_parser('test', help='Run tests (quick subset or full)')
    p_test.add_argument('--quick', action='store_true', help='Run a targeted subset of tests')
    p_test.add_argument('-k', dest='kexpr', help='Pytest -k expression')
    p_test.add_argument('path', nargs='?', help='Optional path to test file/dir')

    p_down = sub.add_parser('down', help='Stop services via docker-compose or stop specific services')
    p_down.add_argument('services', nargs='*', help='Optional list of services to stop (uses compose stop). No args uses compose down')

    sub.add_parser('doctor', help='Check tools, imports, and basic connectivity')

    p_fmt = sub.add_parser('fmt', help='Format code with Black')
    p_fmt.add_argument('paths', nargs='*', help='Optional paths (default: services scripts tests docs *.py)')

    p_lint = sub.add_parser('lint', help='Lint code with Ruff')
    p_lint.add_argument('paths', nargs='*', help='Optional paths (default: services scripts tests)')

    p_type = sub.add_parser('type', help='Type-check with MyPy')
    p_type.add_argument('paths', nargs='*', help='Optional paths (default: services)')

    # Retention cleanup helper
    p_ret = sub.add_parser('retention', help='Run retention cleanup (local)')
    p_ret.add_argument('--dry-run', action='store_true', help='Dry-run (no deletes)')

    # E2E compose smoke test
    sub.add_parser('e2e', help='Run docker-compose E2E smoke test')

    # Ingest load generator
    p_load = sub.add_parser('load', help='Run ingest load test')
    p_load.add_argument('--url', required=True, help='Ingest URL, e.g., http://localhost:8080/api/v2/ingest')
    p_load.add_argument('--api-key', required=True, help='Ingest API key')
    p_load.add_argument('--count', type=int, default=1000, help='Total messages (default: 1000)')
    p_load.add_argument('--threads', type=int, default=10, help='Concurrent workers (default: 10)')
    p_load.add_argument('--timeout', type=float, default=5.0, help='Request timeout seconds (default: 5)')

    args = parser.parse_args(argv)

    if args.command == 'setup':
        return cmd_setup(force=args.force)
    if args.command == 'config':
        return cmd_config(section=args.section, get_key=getattr(args, 'get_key', None), set_kv=getattr(args, 'set_kv', None), publish=getattr(args, 'publish', False), list_keys=getattr(args, 'list_keys', False))
    if args.command == 'logs':
        return cmd_logs(service=args.service, tail=args.tail, follow=args.follow)
    if args.command == 'up':
        return cmd_up(services=args.services)
    if args.command == 'test':
        return cmd_test(quick=args.quick, kexpr=args.kexpr, path=args.path)
    if args.command == 'down':
        return cmd_down(services=args.services)
    if args.command == 'doctor':
        return cmd_doctor()
    if args.command == 'fmt':
        return cmd_fmt(paths=args.paths)
    if args.command == 'lint':
        return cmd_lint(paths=args.paths)
    if args.command == 'type':
        return cmd_type(paths=args.paths)
    if args.command == 'retention':
        return cmd_retention(dry_run=args.dry_run)
    if args.command == 'e2e':
        return cmd_e2e()
    if args.command == 'load':
        return cmd_load(url=args.url, api_key=args.api_key, count=args.count, threads=args.threads, timeout=args.timeout)

    parser.print_help()
    return 1


if __name__ == '__main__':
    sys.exit(main())
