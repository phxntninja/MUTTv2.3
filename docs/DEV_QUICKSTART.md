# MUTT v2.5 – Developer Quickstart

This guide gets you productive quickly with local tools and the developer CLI.

Prerequisites
- Python 3.10+ recommended (3.12 OK)
- Git
- Optional: Docker + Docker Compose (for following logs, running services)

Setup
```bash
git clone https://github.com/YOUR_ORG/mutt.git
cd mutt

# (Optional) Create a virtualenv
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

# Install deps
python -m pip install -r requirements.txt -r tests/requirements-test.txt

# Create .env from template
python scripts/muttdev.py setup
```

Sanity Check
```bash
# Environment doctor
python scripts/muttdev.py doctor

# Fast unit tests
python scripts/muttdev.py test --quick
```

Common Tasks
```bash
# Bring up a service (requires docker-compose.yml)
python scripts/muttdev.py up webui

# Follow service logs (if Docker Compose is available)
python scripts/muttdev.py logs --service webui --follow --tail 200

# Format / lint / type-check
python scripts/muttdev.py fmt
python scripts/muttdev.py lint
python scripts/muttdev.py type
```

Dynamic Config (Redis)
```bash
# List all keys
python scripts/muttdev.py config --list

# Get a key
python scripts/muttdev.py config --get alerter_queue_warn_threshold

# Set a key and notify services
python scripts/muttdev.py config --set alerter_queue_warn_threshold 2000 --publish
```

CI/CD & Code Coverage
The project uses GitHub Actions for continuous integration with strict quality gates:
- **Lint** (Ruff), **Format** (Black), and **Type** (MyPy) checks are build-failing
- Code coverage is tracked via Codecov with automatic PR comments
- Coverage thresholds are enforced (see `codecov.yml`)

**Setting up Codecov (for maintainers):**
1. Sign up at https://codecov.io and link the repository
2. Add `CODECOV_TOKEN` to GitHub repository secrets:
   - Go to repo Settings → Secrets and variables → Actions
   - Add secret named `CODECOV_TOKEN` with the token from Codecov
3. Coverage reports will automatically post to PRs after the secret is configured

**Coverage Configuration:**
- Project coverage must not drop by more than 1% (configurable in `codecov.yml`)
- New code in PRs must have at least 70% coverage
- Coverage XML reports are generated in CI and uploaded as artifacts

Notes
- For integration tests or full stack runs, configure Redis/Postgres/Vault or use Docker Compose.
- When testing, Web UI skips strict config validation to allow app creation without Vault.

