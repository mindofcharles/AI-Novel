# 3-AI Supervisory Team Specification

This document details the operational behavior, decision rules, and recursive escalation logic of the **3-AI Supervisory Team** under the ATT framework.

## 1. Design Paradigm: The 3-AI Committee

To avoid narrative drifts, circular deadlocks, and logical slips within dynamic team debates, every active Agent Team (AT) is audited by a non-participating **Supervisory Team**. The Supervisory Team is composed of exactly 3 specialized AI auditors:

1. **Auditor_Integrity_01** (`Integrity_Auditor`): Verifies database alignment and strict rule adherence.
2. **Auditor_Continuity_02** (`Continuity_Auditor`): Monitors logical timeline and event consistency.
3. **Auditor_Deadlock_03** (`Deadlock_Auditor`): Tracks dialogue progression, repetitive statements, and deadlock scenarios.

The Supervisory Team is entirely non-participating; it does not contribute prose, but audits the multi-agent discussion transcript at the end of each discussion round.

## 2. Dialogue Health Auditing

At the end of a team discussion, the Supervisory Team performs a batch audit of the transcript. It evaluates the debate for:

* **Deadlocks & Repetitions**: Sibling agents repeating the same logical claims without progressing.
* **Role Violations**: Sibling agents stepping outside their assigned role profiles.
* **Logical Mismatches**: Decisions that contradict known database states.

### Audit Output Format

The Supervisory Team produces a strict JSON health evaluation:

```json
{
  "is_healthy": true | false,
  "reason": "Detail reasoning regarding communication efficiency and continuity..."
}
```

## 3. Recursive Parent Escalation Channel

If the dialogue audit results in `is_healthy = False` (indicating a deadlock or severe logic violation), the Supervisory Team triggers the **Recursive Parent Escalation Protocol**:

```plaintext
                   ┌───────────────────────────────┐
                   │    Failed Child Team (AT)     │
                   └───────────────┬───────────────┘
                                   │
                                   ▼
                   ┌───────────────────────────────┐
                   │    Audit Parent Team (AT)     │
                   └───────────────┬───────────────┘
                                   │
                  ┌────────────────┴────────────────┐
                  ▼                                 ▼
            [Parent Healthy]                [Parent Broken]
                  │                                 │
                  ▼                                 ▼
        ┌──────────────────┐              ┌──────────────────┐
        │ Route Failure    │              │ Climb Higher     │
        │ Alert to Parent  │              │ (Escalate up DB) │
        │ Inbox Context    │              └─────────┬────────┘
        └──────────────────┘                        │
                                                    ▼
                                          ┌──────────────────┐
                                          │ Collapse? Route  │
                                          │ to Root AI (L0)  │
                                          └──────────────────┘
```

1. **Climb up the lineage**: The Supervisor resolves the parent team of the failed team.
2. **Audit parent state**: The Supervisor audits the parent team itself.
   * If the parent team is **healthy**, the failure alert (with original anomaly reason and child team ID) is routed directly into the parent team's `message_inbox`. The parent team will consume this context in its next discussion turn and resolve the child deadlock.
   * If the parent team is **also broken**, the Supervisor logs the failure, logs the parent ID, and climbs one level higher up the ancestry tree.
3. **Lineage Collapse Gating**: If the ancestry tree is traversed up to the root and all ancestors are found to be broken, the Supervisor flags a **Lineage Collapse** and escalates a critical system alert directly to the **Level 0 Root AI** (raising a runtime notification).

## 4. Configuration & Usage

The auditing and escalation behaviors are completely automated when `enable_autonomy_suite` is active in `config.yaml`. Anomaly transcripts and escalations are logged dynamically to track overall lineage health.
