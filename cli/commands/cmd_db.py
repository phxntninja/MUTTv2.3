"""
muttdev db - Database management utilities
"""

import os
import subprocess


def register(subparsers):
    """Register the db command."""
    parser = subparsers.add_parser(
        'db',
        help='Database management utilities',
        description='PostgreSQL database management'
    )

    subcommands = parser.add_subparsers(dest='subcommand', help='DB subcommand')

    subcommands.add_parser('shell', help='Open PostgreSQL shell')
    subcommands.add_parser('reset', help='Reset database (WARNING: destroys data)')
    subcommands.add_parser('migrate', help='Run database migrations')
    subcommands.add_parser('backup', help='Create database backup')


def execute(args) -> int:
    """Execute the db command."""
    if not args.subcommand:
        print("Error: No subcommand specified")
        print("Usage: muttdev db <shell|reset|migrate|backup>")
        return 1

    db_host = os.getenv('DB_HOST', 'localhost')
    db_name = os.getenv('DB_NAME', 'mutt')
    db_user = os.getenv('DB_USER', 'postgres')

    if args.subcommand == 'shell':
        return db_shell(db_host, db_name, db_user)
    elif args.subcommand == 'reset':
        return db_reset(db_host, db_name, db_user)
    elif args.subcommand == 'migrate':
        return db_migrate(db_host, db_name, db_user)
    elif args.subcommand == 'backup':
        return db_backup(db_host, db_name, db_user)

    return 0


def db_shell(host: str, dbname: str, user: str) -> int:
    """Open PostgreSQL shell."""
    print(f"Connecting to PostgreSQL: {user}@{host}/{dbname}")
    cmd = ['psql', '-h', host, '-U', user, '-d', dbname]

    try:
        subprocess.run(cmd)
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


def db_reset(host: str, dbname: str, user: str) -> int:
    """Reset database."""
    print("WARNING: This will destroy all data in the database!")
    response = input(f"Type 'yes' to reset database '{dbname}': ")

    if response.lower() != 'yes':
        print("Cancelled")
        return 0

    print("Dropping and recreating database...")

    try:
        # Drop and recreate
        subprocess.run(
            ['psql', '-h', host, '-U', user, '-c', f'DROP DATABASE IF EXISTS {dbname};'],
            check=True
        )
        subprocess.run(
            ['psql', '-h', host, '-U', user, '-c', f'CREATE DATABASE {dbname};'],
            check=True
        )

        # Apply schema
        subprocess.run(
            ['psql', '-h', host, '-U', user, '-d', dbname, '-f', 'database/postgres-init.sql'],
            check=True
        )

        print("✓ Database reset complete")
        return 0

    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        return 1


def db_migrate(host: str, dbname: str, user: str) -> int:
    """Run database migrations."""
    print("Applying database migrations...")

    try:
        subprocess.run(
            ['psql', '-h', host, '-U', user, '-d', dbname, '-f', 'database/postgres-init.sql'],
            check=True
        )
        print("✓ Migrations applied")
        return 0

    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        return 1


def db_backup(host: str, dbname: str, user: str) -> int:
    """Create database backup."""
    from datetime import datetime

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"mutt_backup_{timestamp}.sql"

    print(f"Creating backup: {filename}")

    try:
        with open(filename, 'w') as f:
            subprocess.run(
                ['pg_dump', '-h', host, '-U', user, '-d', dbname],
                stdout=f,
                check=True
            )

        print(f"✓ Backup created: {filename}")
        return 0

    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        return 1
