# Dependabot Quick Reference Commands

## Quick Actions

### Option 1: Use the Interactive Script (Easiest)

```bash
cd "C:\DEV_area\AI Work\MUTTv2.5"
./cleanup_dependabot_branches.sh
```

### Option 2: Manual Commands

#### Delete ONLY the redis branch (Recommended)
```bash
cd "C:\DEV_area\AI Work\MUTTv2.5"
git push origin --delete dependabot/pip/redis-7.0.1
```

#### Delete ALL Dependabot branches
```bash
cd "C:\DEV_area\AI Work\MUTTv2.5"
git push origin --delete \
  dependabot/github_actions/actions/checkout-5 \
  dependabot/github_actions/actions/setup-python-6 \
  dependabot/github_actions/codecov/codecov-action-5 \
  dependabot/github_actions/docker/build-push-action-6 \
  dependabot/pip/coverage-7.10.7 \
  dependabot/pip/pytest-8.4.2 \
  dependabot/pip/pytest-flake8-1.3.0 \
  dependabot/pip/pytest-xdist-3.8.0 \
  dependabot/pip/redis-7.0.1
```

#### Commit updated Dependabot config
```bash
cd "C:\DEV_area\AI Work\MUTTv2.5"
git add .github/dependabot.yml
git commit -m "Configure Dependabot to ignore redis and pytest major versions"
git push origin main
```

#### Verify cleanup
```bash
cd "C:\DEV_area\AI Work\MUTTv2.5"
git fetch --prune origin
git branch -r | grep dependabot
# Should return nothing
```

## Test Pytest 8.4.2 Locally

```bash
cd "C:\DEV_area\AI Work\MUTTv2.5"
python3.10 -m venv test_venv
source test_venv/bin/activate  # Windows: test_venv\Scripts\activate
pip install -r requirements.txt
pip install pytest==8.4.2 pytest-cov pytest-mock pytest-xdist
pytest tests/ -v
```

**Result**:
- ✅ Tests pass → Merge the pytest PR on GitHub
- ❌ Tests fail → Close and delete the pytest PR on GitHub

## Full Documentation

See `DEPENDABOT_CLEANUP_GUIDE.md` for detailed explanations and step-by-step instructions.
