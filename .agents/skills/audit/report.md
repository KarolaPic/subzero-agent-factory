# Report

The format every audit returns. Domain skills use the same severity words, so their findings drop into this report unchanged.

## Severity

| Severity | Meaning |
| --- | --- |
| `HIGH` | Breaks behaviour or loses work: a dropped feature, a control that does nothing, a committed secret or "done" with no look |
| `MEDIUM` | Visible and inconsistent: a duplicate component, a wrong-case label, a clipped edge, an unrequested addition or a hand-written report |
| `LOW` | Polish: a word too many, a narrating comment or a missing screenshot |

When two levels fit, take the higher one and say why in the finding.

## Shape

Lead with the scope and the verdict, then the coverage, the numbered findings and the summary. The same parts fill `report.js` for [report.html](report.html), in the shape its header comment shows.

```
Scope: uncommitted diff, 14 files, 3 requests in this thread
Verdict: Block, 2 HIGH

Coverage
| Skill | Inspected | Result |
| --- | --- | --- |
| verify | Settings and Library opened | 1 finding |
| scope | requests 1 to 3 | 1 finding |
| copy | 9 strings | Clean |
| match | no reference named | Skipped |

Findings
1. HIGH  settings/index.tsx:42 - [verify-click-new-controls] "Reset" has no handler
2. HIGH  request 2 - [scope-keep-what-worked] the back button is gone after the refactor
3. MEDIUM  library/styles.module.css:18, menu/styles.module.css:7 - [reuse-no-local-restyle] local radius on the shared Menu

Summary
| Rule | Count | Severity |
| --- | --- | --- |
| verify-click-new-controls | 1 | HIGH |
| scope-keep-what-worked | 1 | HIGH |
| reuse-no-local-restyle | 2 | MEDIUM |

Not verified: export, it needs a signed build
```

## Rules for the report

- Each finding is `file:line - [rule-id] what is wrong`. Use `request N` or `step N` when no file applies.
- One number per root cause. List every location of that cause on its line.
- A skill with nothing to check is `Skipped` with the reason. A skill that found nothing is `Clean`.
- `Not verified` lists every check that could not run and why.
- End with the question of which numbers to fix.
