# Database Management Committee (DMC) Specification

This document details the operational behavior, safety constraints, and transaction auditing of the **Database Management Committee (DMC)** under the ATT framework.

## 1. Design Paradigm: The 3-AI Transaction Security Guard

Direct transactions on the SQLite memory store represent a high-priority narrative integrity surface. An unchecked or flawed query could resurrect a deceased character, drop schemas, or corrupt character status histories.

To safeguard the narrative database, a specialized **Database Management Committee (DMC)** is spawned under `ATTManager`, composed of exactly 3 specialized database auditors:

1. **Integrity_Auditor** (`Integrity_Auditor`): Verifies column schema compliance and structural fact preservation.
2. **Continuity_Auditor** (`Continuity_Auditor`): Cross-references query parameters against the timeline and character status directories (guarding against logical timeline jumps or resurrecting dead characters).
3. **Security_Auditor** (`Security_Auditor`): Scans direct queries for SQL injection, dangerous drops/deletes, or malicious schema corruption.

## 2. Dynamic Interception Flow

Every SQL transaction executing on the Memory database is intercepted and vetted before committing:

```plaintext
      [ SQL Query Execution ]
                │
                ▼
  ┌───────────────────────────┐
  │  DMC audit_query Check    │
  └─────────────┬─────────────┘
                │
        ┌───────┴───────┐
        ▼               ▼
   [Approved]      [Rejected]
        │               │
        ▼               ▼
  ┌───────────┐   ┌───────────────┐
  │ Commit to │   │ Discard Query │
  │ SQLite DB │   │ Return Error  │
  └───────────┘   └───────────────┘
```

1. **Interception**: Direct executions inside the memory and tool layer are intercepted by DMC.
2. **Auditing**: The 3-AI Committee performs a rapid safety audit of the raw SQL query.
3. **Commit/Rejection Gating**:
   * **Approved**: The query continues to run on SQLite under atomic transaction safety.
   * **Rejected**: The query is discarded, transaction commits are rolled back, and a structured `DMC Rejection Error` is returned to the agent, halting execution to protect database integrity.

## 3. Strict Safety Auditing Rules

The DMC evaluates SQLite commands against rigorous validation gates:

| Safety Gate | Description | Action on Violation |
| :--- | :--- | :--- |
| **Resurrection Prevention** | Any query attempting to change character status from `'dead'` back to `'alive'` or `'missing'`. | **REJECT** (Prevents illegal character resurrections) |
| **SQL Injection Check** | Raw commands containing suspected injection signatures or unauthorized sub-queries. | **REJECT** (Prevents SQL injection) |
| **Schema Drops / Alters** | Query containing destructive keywords like `DROP TABLE`, `ALTER TABLE`, or unauthorized `TRUNCATE`. | **REJECT** (Prevents structural loss) |
| **Global Rule Violations** | Updates that violate strict category rules stored in the World Bible. | **REJECT** (Prevents logical continuity breaks) |

### Auditing Output Protocol

The DMC evaluates queries and returns a clear decision tuple:

* **`approved`**: `True` or `False`.
* **`reason`**: Detailed explanation if the query was rejected, allowing ReAct agents to inspect the failure, adjust their queries, and retry safely.

## 4. Integration & Configuration

The DMC is registered automatically on startup by `AutonomyWorkflowMixin.initialize_autonomy()` and bound directly to `MemoryManager`. No manual queries bypass the DMC when autonomy mode is active.
