"""
muttdev test - Run MUTT tests
"""

import subprocess
import sys


def register(subparsers):
    """Register the test command."""
    parser = subparsers.add_parser(
        'test',
        help='Run MUTT tests',
        description='Run unit and integration tests'
    )

    parser.add_argument('--unit', action='store_true', help='Run unit tests only')
    parser.add_argument('--integration', action='store_true', help='Run integration tests only')
    parser.add_argument('--coverage', action='store_true', help='Generate coverage report')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('pattern', nargs='?', help='Test file pattern')


def execute(args) -> int:
    """Execute the test command."""
    cmd = ['pytest']

    if args.verbose:
        cmd.append('-v')

    if args.coverage:
        cmd.extend(['--cov=services', '--cov-report=html', '--cov-report=term'])

    if args.unit:
        cmd.extend(['-m', 'unit'])
    elif args.integration:
        cmd.extend(['-m', 'integration'])

    if args.pattern:
        cmd.append(args.pattern)
    else:
        cmd.append('tests/')

    print(f"Running: {' '.join(cmd)}")
    print()

    try:
        result = subprocess.run(cmd)
        return result.returncode
    except KeyboardInterrupt:
        print("\nTests interrupted")
        return 130
