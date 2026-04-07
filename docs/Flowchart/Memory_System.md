# Memory & Retrieval System

This document details the multi-tier retrieval funnel and the atomic commit/rollback mechanism used to ensure narrative consistency.

## 1. Context Retrieval Funnel (The Narrowing Funnel)

The system avoids "context pollution" by filtering and ranking facts through a 5-step pipeline.

```mermaid
flowchart TD
    Start[Request Context: Task Type + State] --> Intent{1. Intent Classification}
    
    Intent -- continuity_build --> Depth[Low Recall: Focus on recent entities]
    Intent -- continuity_guard --> Depth[High Recall: Broad entity/conflict scan]
    
    Depth --> SQLite[2. SQLite Pre-filter]
    SQLite -- "Fetch T1 Rules + T2 Chars/Events" --> Semantic[3. FAISS Semantic Search]
    
    Semantic -- "Fetch T3 Lore/Atmosphere" --> Align{4. Cross-Tier Alignment}
    
    Align -- "Filter: Contradicts T1/T2? (e.g. Dead char action)" --> Rerank[5. Semantic Reranking]
    
    Rerank -- "Score = Similarity + Token Overlap Bonus" --> Final[Final Context Package]
```

### Reranking Heuristics

* **Entity Bonus**: +0.35 score for each focus entity token match.
* **Location Bonus**: +0.50 score for exact location match.

## 2. Atomic Chapter Commit (Scanner ↔ Memory)

Ensures that "dirty" facts from a bad scan don't corrupt the long-term memory.

```mermaid
sequenceDiagram
    autonumber
    participant W as WorkflowManager
    participant M as MemoryManager
    participant DB as SQLite
    participant V as FAISS Index
    participant CQ as Conflict Queue

    W->>M: begin_batch()
    M->>DB: BEGIN TRANSACTION
    M->>V: faiss.clone_index(current_index)
    Note over M, V: Snapshot created for safety

    W->>M: apply_fact_payload(JSON)
    
    loop Per Fact (Rule/Char/Event)
        M->>M: Conflict Heuristics Check
        alt BLOCKING Conflict Found
            M-->>W: Raise Conflict Exception
        else Safe or NON_BLOCKING
            M->>DB: Staging write
        end
    end

    alt All Safe
        W->>M: end_batch(success=True)
        M->>DB: COMMIT
        Note over M, V: Discard Snapshot
        M-->>W: Status: COMPLETED
    else Error/Blocking
        W->>M: end_batch(success=False)
        M->>DB: ROLLBACK
        M->>V: Restore index from Snapshot
        M-->>W: Status: FAILED
    end
```

## 3. Conflict Detection Heuristics

The system doesn't just match keywords; it checks for semantic contradictions:

* **Character Status Guard**: Blocks "Resurrection" (Dead -> Alive) or changing core identities.
* **Rule Contradiction**:
  * **Negation Detection**: Matches "never/no/not" against positive counterparts.
  * **Polarity Mapping**: Detects antonym pairs (e.g., "forbidden" vs "allowed").
* **Weighted Overlap**: Uses a custom weight table (e.g., "kill", "die", "death" have high weights) to detect critical timeline clashes.
