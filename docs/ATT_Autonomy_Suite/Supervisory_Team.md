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

## 3. Asynchronous Parent Escalation Channel

If the dialogue audit results in `is_healthy = False` (indicating a deadlock or severe logic violation), the Supervisory Team triggers the **Asynchronous Escalation Protocol**:

```plaintext
                   ┌───────────────────────────────┐
                   │    Failed Child Team (AT)     │
                   └───────────────┬───────────────┘
                                   │ (Supervisory Audit Fails)
                                   ▼
                   ┌───────────────────────────────┐
                   │ Dispatch Alert to Direct      │
                   │ Parent's Message Inbox        │
                   └───────────────┬───────────────┘
                                   │
                                   ▼
                   ┌───────────────────────────────┐
                   │ Audit Parent Team (AT)        │
                   │ consumes alert in its next    │
                   │ discussion turn autonomously  │
                   └───────────────────────────────┘
```

1. **Direct Escalation**: The Supervisor resolves the direct parent team of the failed team.
2. **Asynchronous Routing**: The Supervisor dispatches a failure alert (containing the anomaly reason and child team ID) directly into the parent team's `message_inbox`. It returns immediately, preventing synchronous blocking loops that cause API timeouts.
3. **Context Consumption**: The parent team will consume this context in its next discussion turn, automatically summarizing the inbox if the cascade of errors exceeds the `inbox_summarize_threshold_chars` threshold.
4. **Fallback Gating**: If no parent exists in the lineage tree, the Supervisor escalates a critical system alert directly to the **Level 0 Root AI**.

## 4. Configuration & Usage

The auditing and escalation behaviors are completely automated when `enable_autonomy_suite` is active in `config.yaml`. Anomaly transcripts and escalations are logged dynamically to track overall lineage health.
