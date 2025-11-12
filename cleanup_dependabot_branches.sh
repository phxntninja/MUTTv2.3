#!/bin/bash
# MUTT v2.5 - Dependabot Branch Cleanup Script
# This script helps clean up Dependabot branches

set -e

cd "C:\DEV_area\AI Work\MUTTv2.5"

echo "================================================"
echo "MUTT v2.5 - Dependabot Branch Cleanup"
echo "================================================"
echo ""

# Function to prompt user
prompt_user() {
    read -p "$1 (y/n): " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]]
}

echo "Current Dependabot branches:"
git branch -r | grep dependabot | sed 's/^ */  /'
echo ""

echo "Cleanup Options:"
echo "  1. Delete ONLY the redis branch (recommended)"
echo "  2. Delete ALL Dependabot branches (bulk cleanup)"
echo "  3. Show detailed branch info"
echo "  4. Exit (I'll handle manually via GitHub)"
echo ""

read -p "Enter choice (1-4): " choice

case $choice in
  1)
    echo ""
    echo "Deleting redis branch (locked to 5.0.1 for RHEL 8)..."
    if prompt_user "Delete dependabot/pip/redis-7.0.1?"; then
      git push origin --delete dependabot/pip/redis-7.0.1
      echo "✅ Redis branch deleted"
    else
      echo "❌ Skipped"
    fi
    ;;

  2)
    echo ""
    echo "⚠️  WARNING: This will delete ALL 9 Dependabot branches!"
    echo ""
    echo "You should only do this if:"
    echo "  - You don't want any of the proposed updates"
    echo "  - You prefer to manage updates manually"
    echo ""
    if prompt_user "Are you sure you want to delete ALL Dependabot branches?"; then
      echo ""
      echo "Deleting all Dependabot branches..."
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
      echo ""
      echo "✅ All Dependabot branches deleted"
    else
      echo "❌ Aborted - no branches deleted"
    fi
    ;;

  3)
    echo ""
    echo "=== Detailed Branch Information ==="
    echo ""
    for branch in $(git branch -r | grep dependabot | sed 's/^ *//'); do
      echo "Branch: $branch"
      commits=$(git rev-list --count origin/main..$branch 2>/dev/null)
      echo "  Commits ahead: $commits"
      date=$(git log -1 --format="%ci" $branch 2>/dev/null)
      echo "  Last commit: $date"
      echo ""
    done
    echo "Run this script again to perform cleanup."
    ;;

  4)
    echo ""
    echo "✅ No changes made. Handle cleanup manually via GitHub UI."
    echo ""
    echo "See DEPENDABOT_CLEANUP_GUIDE.md for detailed instructions."
    exit 0
    ;;

  *)
    echo ""
    echo "❌ Invalid choice. Exiting."
    exit 1
    ;;
esac

echo ""
echo "================================================"
echo "Next Steps:"
echo "================================================"
echo ""
echo "1. Commit the updated .github/dependabot.yml:"
echo "   git add .github/dependabot.yml"
echo "   git commit -m 'Configure Dependabot to ignore redis'"
echo "   git push origin main"
echo ""
echo "2. See DEPENDABOT_CLEANUP_GUIDE.md for:"
echo "   - Merging safe branches via GitHub"
echo "   - Testing pytest 8.4.2 locally"
echo "   - Verification steps"
echo ""
echo "✅ Done!"
