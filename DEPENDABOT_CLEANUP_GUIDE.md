# Dependabot Branch Cleanup Guide

**Date**: 2025-11-12
**Status**: 9 Dependabot branches pending review

---

## Summary

All 9 Dependabot branches were created on November 10, 2025 and have NOT been merged into main.

### Branch Categorization

| Status | Count | Action |
|--------|-------|--------|
| ✅ Safe to merge | 7 | Merge via GitHub PRs |
| ⚠️ Needs testing | 1 | Test locally, then merge or delete |
| ❌ Do not merge | 1 | Close PR and delete branch |

---

## Detailed Branch Analysis

### ✅ Category 1: Safe to Merge (7 branches)

These are low-risk updates that should be merged:

#### GitHub Actions Updates (4 branches)
- `origin/dependabot/github_actions/actions/checkout-5` (v4 → v5)
- `origin/dependabot/github_actions/actions/setup-python-6` (v5 → v6)
- `origin/dependabot/github_actions/codecov/codecov-action-5` (v4 → v5)
- `origin/dependabot/github_actions/docker/build-push-action-6` (v4 → v6)

#### Python Test Dependencies (3 branches)
- `origin/dependabot/pip/coverage-7.10.7` (7.4.0 → 7.10.7)
- `origin/dependabot/pip/pytest-flake8-1.3.0` (1.1.1 → 1.3.0)
- `origin/dependabot/pip/pytest-xdist-3.8.0` (3.5.0 → 3.8.0)

### ⚠️ Category 2: Needs Testing (1 branch)

- `origin/dependabot/pip/pytest-8.4.2` (7.4.3 → 8.4.2) - **Major version bump**

**Action Required**: Test locally before merging.

### ❌ Category 3: Do Not Merge (1 branch)

- `origin/dependabot/pip/redis-7.0.1` (5.0.1 → 7.0.1)

**Reason**: Redis 5.0.1 is intentionally locked for RHEL 8 compatibility (see requirements.txt comment).

---

## Step-by-Step Cleanup Instructions

### Step 1: Merge Safe Updates (via GitHub UI)

For each of the 7 safe branches:

1. Go to GitHub → Pull Requests
2. Find the PR for each branch
3. Review changes (should be version bumps only)
4. Wait for CI to pass (if configured)
5. Click "Merge pull request"
6. Delete branch after merge

**Expected branches to merge**:
- actions/checkout-5
- actions/setup-python-6
- codecov/codecov-action-5
- docker/build-push-action-6
- pip/coverage-7.10.7
- pip/pytest-flake8-1.3.0
- pip/pytest-xdist-3.8.0

### Step 2: Test Pytest 8.4.2 Locally

```bash
cd "C:\DEV_area\AI Work\MUTTv2.5"

# Create a temporary test environment
python3.10 -m venv test_venv
source test_venv/bin/activate  # Windows: test_venv\Scripts\activate

# Install dependencies with new pytest
pip install -r requirements.txt
pip install pytest==8.4.2 pytest-cov pytest-mock pytest-xdist

# Run full test suite
pytest tests/ -v

# Check results:
# - If ALL tests pass → Merge the PR on GitHub
# - If ANY tests fail → Close PR and delete branch on GitHub
```

**Decision**:
- ✅ Tests pass → Merge PR on GitHub, delete branch
- ❌ Tests fail → Close PR on GitHub, delete branch, keep pytest 7.4.3

### Step 3: Close and Delete Redis Branch

Since redis is intentionally locked to 5.0.1:

**On GitHub**:
1. Go to Pull Requests
2. Find PR for `dependabot/pip/redis-7.0.1`
3. Comment: "Closing - redis locked to 5.0.1 for RHEL 8 compatibility"
4. Click "Close pull request"
5. Click "Delete branch"

**Or via command line**:
```bash
cd "C:\DEV_area\AI Work\MUTTv2.5"
git push origin --delete dependabot/pip/redis-7.0.1
```

### Step 4: Commit Updated Dependabot Config

The dependabot.yml file has been updated to prevent future noise:

```bash
cd "C:\DEV_area\AI Work\MUTTv2.5"
git add .github/dependabot.yml
git commit -m "Configure Dependabot to ignore redis and pytest major versions

- Ignore redis updates (locked to 5.0.1 for RHEL 8 compatibility)
- Ignore pytest major version updates (requires manual testing)
- Change schedule from weekly to monthly to reduce noise
- Group related updates together (test deps, GitHub actions)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

git push origin main
```

---

## Alternative: Bulk Delete All Branches

If you prefer to delete all Dependabot branches and manage updates manually:

```bash
cd "C:\DEV_area\AI Work\MUTTv2.5"

# Delete all Dependabot branches at once
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

echo "All Dependabot branches deleted"
```

**Note**: You'll still want to commit the updated `.github/dependabot.yml` to prevent future PRs for redis.

---

## Dependabot Configuration Changes

The `.github/dependabot.yml` file has been updated with:

### Changes Made:
1. **Schedule**: `weekly` → `monthly` (reduces noise)
2. **Ignore Rules Added**:
   - Redis: Ignore all major and minor updates (locked to 5.0.1)
   - Pytest: Ignore major version updates (requires manual testing)
3. **Grouping Added**:
   - Test dependencies grouped together (fewer PRs)
   - GitHub Actions grouped together (fewer PRs)

### Future Behavior:
- ✅ Dependabot will NOT create PRs for redis updates
- ✅ Dependabot will NOT create PRs for pytest 8.x or higher
- ✅ Minor pytest updates (7.x) will still be proposed
- ✅ GitHub Actions updates will be grouped into single PRs
- ✅ Test dependency minor updates will be grouped

---

## Verification

After cleanup, verify no Dependabot branches remain:

```bash
cd "C:\DEV_area\AI Work\MUTTv2.5"
git fetch --prune origin
git branch -r | grep dependabot
```

**Expected output**: (empty - no results)

---

## Summary Checklist

- [ ] Merged 7 safe branches via GitHub UI
- [ ] Tested pytest 8.4.2 locally
  - [ ] If passed: Merged pytest PR
  - [ ] If failed: Closed and deleted pytest PR
- [ ] Closed and deleted redis PR
- [ ] Committed updated `.github/dependabot.yml`
- [ ] Pushed changes to main
- [ ] Verified no Dependabot branches remain

---

## Questions?

- **Why keep redis at 5.0.1?** - Matches RHEL 8 Redis version for compatibility
- **Why ignore pytest major versions?** - Breaking changes need manual testing
- **Can I re-enable weekly updates?** - Yes, change `interval: "monthly"` back to `"weekly"` in dependabot.yml
- **Will this delete old PRs?** - No, closed PRs remain in GitHub history

---

**Status**: Ready for cleanup ✅
