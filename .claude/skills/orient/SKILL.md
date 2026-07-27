---
name: orient
description: Reconstruct where scalpbot stands and propose the next
  move. Use at the start of a session when returning after time away,
  after a /clear or /compact, or any time you (the human) don't remember
  what's next.
---

# Orient

You are bringing a returning developer back up to speed on scalpbot. They do
NOT hold this project's state in their head — that's the whole point. Do not
assume they know what's next.

1. Run `git log --oneline -15`, `git status`, `git diff --stat` — what
   changed, what's uncommitted.
2. Read the newest file in `.claude/plans/` (plansDirectory in
   `.claude/settings.json`). What did it set out to do, and how much does
   the git history suggest is done?
3. Run each gate script in `gates/` (`gate0_edge.py`, `gate0_drawdown.py`,
   `gate1_infra.py`, `gate4_shadow.py`, `gate5_live.py`) and report
   PASS/FAIL for each. Per PLAN.md §9, gates fail closed — an unimplemented
   gate is a FAIL, not an unknown. The first FAIL is the phase boundary:
   nothing beyond it should be built yet.
4. Skim CLAUDE.md and PLAN.md for current constraints, and `research/ledger.md`
   for the latest logged experiment (empty ledger = Phase 0 edge work hasn't
   produced a result yet).
5. Scan for recent TODO/FIXME and any half-edited files.

Then a briefing, max ~200 words:
- Where we are: which phase gate is the current boundary; what was last
  worked on; committed vs in-flight.
- Open threads: anything unfinished or risky.
- Next moves: 2-3 concrete candidates, one sentence each, each naming the
  files it would touch. Candidates must respect the phase gate — do not
  propose Phase 1+ infrastructure work while Phase 0 (`gate0_edge.py`,
  `gate0_drawdown.py`) hasn't passed.

End by asking which to take. When they pick, enter Plan Mode (don't edit)
and plan that step.
