# Claude Code Configuration Directory

This directory contains helper files for managing Claude Code sessions efficiently.

---

## 📁 Files in This Directory

### `budget-check-prompts.md`
Quick-reference prompts for:
- Checking token budget
- Creating handoffs
- Session management
- Emergency stops

**Usage:** Copy-paste prompts when needed

---

## ⚙️ How to Use These Prompts

### Every Hour (or after major task completion):
```bash
# Just ask me:
"Budget check - how are we doing?"
```

### When approaching limits (60%, 75%, 85%):
```bash
# I'll proactively warn you, but you can also ask:
"Should we create a handoff now?"
```

---

## 🎯 Quick Reference

**Current Session:**
- Started: 2025-11-09
- Phase 1: ✅ Complete (8/8 tasks)
- Tokens: ~120k/200k used (60%)
- Last handoff: AI_COLLABORATION_HANDOFF.md

**Next Checkpoint:**
- At 75% (150k tokens) - create new handoff
- At 85% (170k tokens) - emergency stop

---

## 💡 Pro Tips

1. **Ask for budget checks** - I can't automatically monitor, but I'll always tell you honestly when asked
2. **Use TodoWrite** - Add "Check budget after Task X.Y" to your todo list
3. **Set phone timer** - Remind yourself every 30-60 minutes
4. **Batch tasks** - Complete 2-3 tasks before asking for budget check

---

## 🤖 Why Can't Claude Auto-Check?

I don't have:
- ❌ Cron/scheduled task capabilities
- ❌ Background monitoring
- ❌ Autonomous file creation triggers

But I CAN:
- ✅ Tell you usage when asked
- ✅ Recommend when to handoff
- ✅ Create handoffs on request
- ✅ Track via TodoWrite

**Solution:** You control the timing, I provide the data!

---

## 📝 Workflow Example

**Good Session Pattern:**

```
9:00 AM - Start session
        → "Budget check, what should we work on?"

9:30 AM - After Task 1
        → Continue (momentum!)

10:00 AM - After Task 2
         → "Budget check?"
         → Continue if <70%, handoff if >70%

10:30 AM - Natural break
         → "Create session summary"
         → Handoff if needed
```

**Bad Session Pattern:**

```
❌ Work for 3 hours straight without checking
❌ Hit 95% usage and lose context
❌ No handoff created
❌ Have to start over
```

---

## 🔄 Update This File

Feel free to update this README as you develop your own workflow!

Current best practices will be added here as we learn what works.

---

**Remember:** Just ask "Budget check?" anytime! 🚀
