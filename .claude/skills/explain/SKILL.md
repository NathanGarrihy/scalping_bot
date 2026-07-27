---
name: explain
description: Teach the developer how part of scalpbot works, deep enough
  to defend in a technical interview. Use when they ask to understand the
  project, architecture, or a feature, or to prep for interviews. Arg like
  "architecture" or "feature: state machine"; append --quiz for Socratic
  mode.
---

# Explain (interview-grade)

Interviewers probe decisions and trade-offs, not just behavior. The goal is
that the developer can DEFEND this code, not recite it.

Arg ($ARGUMENTS): `architecture` (or empty) = whole project;
`feature: <name>` = one module (e.g. `feature: state machine`,
`feature: hostile fill model`, `feature: rate-limit budgeter`); append
`--quiz` for quiz mode.

Do the heavy reading via the Explore subagent (use Sonnet, not Haiku —
comprehension matters here) so the main context stays clean. Then write to
`docs/interview-prep/<topic>.md` (create the dir) and summarize inline.

Each explainer, in order:
1. What it does — 2-3 plain sentences.
2. How it works — real data/control flow, naming actual files and types
   (e.g. `core/state_machine.py`, `core/events.py`, `venues/base.py`).
3. Why this way — the decisions made, and the alternatives considered and
   rejected, with reasons. Ground this in PLAN.md where the reasoning is
   already documented (venue choice, hostile fill model, purged/embargoed
   walk-forward, journal-before-send) rather than inventing justification.
4. Failure modes & edge cases — what breaks it, what it guards against.
5. At scale / what you'd change — honest limits, next iteration.
6. Likely questions — 5-8 an interviewer would actually ask, each with a
   strong, specific answer in the developer's own first-person voice
   referencing the real code.

Quiz mode (--quiz): do NOT hand over answers. Ask one question at a time,
wait, then critique their answer — what was strong, what was vague, what
an interviewer would push on next. Continue until they answer cleanly.
