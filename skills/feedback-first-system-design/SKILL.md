# Feedback-first System Design

> Status: draft
> Version: 0.1.0
> Risk: low
> Node: d71cc0c2-a2ad-4bb4-b397-95e38afd13c9

## Triggers
- designing automated evaluation or evolution loops
- adding review gates or approval workflows
- LLM-generated tests or artifacts need validation
- system has final tests, telemetry, feedback, rollback, or scoring already
- 设计自动化评测、技能进化、出题、反馈闭环、审批流程时

## Preconditions
- The system can observe outcomes through tests, telemetry, scoring, usage feedback, or rollback.
- Failures are mostly reversible or can be automatically downgraded, retried, or marked for revision.
- There is a temptation to add manual review because quality is uncertain.

## Procedure
1. Identify the final feedback loop first: real run, test, judge, telemetry, user feedback, rollback, or regression tracking.
2. Add only hard filters in the middle: empty fields, malformed structure, unsafe content, obvious lack of grounding, irreversible risk.
3. Do not add soft manual review when final automated evaluation can judge quality.
4. Ground generated artifacts in source evidence such as memories, failures, triggers, procedures, verification, and known failure modes.
5. Let validated artifacts enter the executable feedback loop directly.
6. Use outcomes to promote, downgrade, retry, or create regression cases.
7. Escalate to humans only for privacy, money, safety, external publication, irreversible actions, or repeated systemic failure.

## Verification
A proposed design should show fewer manual gates, explicit hard filters, an executable feedback loop, automatic downgrade/rollback behavior, and evidence that generated artifacts are grounded in source material.

## Failure Modes
- Turning uncertainty into pending_review/manual_approval by default.
- Using approval workflows to hide missing telemetry or weak evaluation.
- Letting smoke tests, dry-runs, or static format scores count as real evidence.
- Adding middle-layer subjective quality review when the final loop already judges quality.
- Allowing generated artifacts without source grounding.

## Evidence
### Source Nodes
- fda9dcd9
- 5360f2d9
- 1c3f4a7f
- 0a8ac305

### Verification Nodes
- None

## Metadata
```json
{
  "latest_format_check": {
    "mnemosyne_score": 82.0,
    "darwin_score": 72.9,
    "final_score": 77.5,
    "checked_at": "2026-05-14T04:03:06.733313+00:00"
  }
}
```
