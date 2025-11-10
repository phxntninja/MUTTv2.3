# Claude Code Budget Check Prompts

This file contains prompts you can use to check budget and create handoffs.

---

## 📊 Quick Budget Check

**Paste this every hour or after major tasks:**

```
Quick budget check: How many tokens have we used and how many remain? Should we create a handoff?
```

**Expected response:**
- Current token usage percentage
- Recommendation on whether to continue or handoff

---

## 🚨 Budget Alert Thresholds

**Create handoff when:**
- ✅ 60% used (120,000 tokens) - **WARNING** - Good stopping point after completing current task
- ✅ 75% used (150,000 tokens) - **CRITICAL** - Create handoff NOW
- ✅ 85% used (170,000 tokens) - **STOP** - Emergency handoff, may lose context soon

---

## 📝 Quick Handoff Generator

**Paste this when hitting a threshold:**

```
We've hit [60%/75%/85%] token usage. Create a comprehensive handoff document including:
1. What we completed since last handoff
2. Current task status
3. Next recommended tasks
4. Any blockers or issues
5. File inventory
6. How other AIs should help

Save as HANDOFF_[DATE]_[PERCENTAGE].md
```

---

## ⏰ Session Checkpoints

**Start of session (first message):**
```
Starting new session. What's our current token budget and what should we prioritize?
```

**After each major task:**
```
Task [X.Y.Z] complete. Budget check - can we continue or should we handoff?
```

**End of session:**
```
I'm taking a break. Create a session summary with:
- What we accomplished
- Token usage
- Next steps for when I return
```

---

## 🎯 Proactive Budget Alerts

**You can ask me to track this in todos:**

```
Add a todo: "Check token budget after every 2 tasks completed"
```

Then I'll remind you via the todo list.

---

## 💡 Smart Workflow

**High-efficiency approach:**

1. **Session Start** (5 min)
   - Check budget
   - Review last handoff
   - Plan 2-3 tasks

2. **Work Phase** (30-45 min)
   - Complete batched tasks
   - Minimal back-and-forth
   - Use TodoWrite for tracking

3. **Budget Check** (2 min)
   - Quick status check
   - Decide: continue or handoff?

4. **Session End** (5 min)
   - Create handoff if needed
   - Push to GitHub
   - Update task tracker

---

## 📋 Copy-Paste Templates

### Template 1: Quick Status
```
Status check:
- Tokens used: ?
- Tasks completed: ?
- Should we continue: ?
```

### Template 2: Handoff Request
```
Create handoff now. Include:
- Phase/section completed
- Files created/modified
- Tests status
- Next priority tasks
- Critical notes for next AI
```

### Template 3: Emergency Stop
```
Emergency handoff needed. Token budget critical.
Create comprehensive handoff including all context needed to resume.
```

---

## 🤖 Integration with Other Tools

**VS Code Claude Extension:**
- Has separate token budget
- Use for small edits after handoff
- Doesn't affect CLI budget

**Gemini Extension:**
- Use for reviews
- Doesn't use Claude budget
- Good for code quality checks

**Strategy:**
- Claude CLI for bulk work (track budget!)
- VS Code Claude for quick edits
- Gemini for reviews
- Rotate to maximize efficiency

---

## 📊 Manual Budget Tracking

If you want to track manually:

```bash
# Create a simple log file
echo "Session 1: Phase 1 Complete - 118k/200k tokens (59%)" >> budget_log.txt
echo "Session 2: [pending]" >> budget_log.txt
```

---

## ⚡ Power User Tip

**Set a timer on your phone:**
- Every 30 minutes: Ask "Budget check?"
- Every hour: Ask "Should we create a handoff?"
- Before breaks: Always create handoff

This prevents losing work if token limit hits unexpectedly.

---

## 🎯 Current Session Status

**Last updated:** 2025-11-09

**Current usage:** 118k/200k (59%)

**Last handoff:** AI_COLLABORATION_HANDOFF.md (Phase 1 complete)

**Next checkpoint:** 120k tokens (60% - after 2k more tokens)

**Next handoff:** 150k tokens (75% - after 32k more tokens)

---

**Remember:** You control when we check budget. Just ask! I'll always give you an honest assessment of whether we should continue or create a handoff.
