# World Building & Framework Flow

This document details the strategic planning phase where the world setting and plot frames are established.

## 1. Project Initialization Phase (Architect ↔ Critic)

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant W as WorkflowManager
    participant A as Architect Agent
    participant C as Critic Agent
    participant M as Memory (Initial Seed)

    U->>W: --start (with Novel_Overview.md)
    W->>A: generate_world_bible(overview)
    A-->>W: World Bible Draft (Markdown)
    
    loop World Discussion Rounds (config.WORLD_DISCUSSION_ROUNDS)
        W->>C: review_world_bible(draft)
        C-->>W: Critique (Logic, Conflicts, Depth)
        W->>A: revise_world_bible(draft, critique)
        A-->>W: Revised World Bible
    end

    W->>W: Save Final World Bible to novel/frame/world/
    W->>M: Scanner extracts initial Fact JSON from Bible
    M-->>W: Seed SQLite & FAISS
```

## 2. Strategic Plot Planning (Planner ↔ Critic)

```mermaid
sequenceDiagram
    autonumber
    participant W as WorkflowManager
    participant P as Planner Agent
    participant C as Critic Agent

    Note over W, C: Phase 2A: High-Level Plot Outline
    W->>P: generate_plot_outline(World Bible)
    P-->>W: Plot Outline Draft
    loop Plot Discussion Rounds
        W->>C: review_plot(draft)
        C-->>W: Critique (Pacing, Arc Consistency)
        W->>P: revise_plot(draft, critique)
        P-->>W: Revised Plot Outline
    end

    Note over W, C: Phase 2B: Detailed Plot Outline (Scene Clusters)
    W->>P: generate_detailed_plot(World Bible + Plot Outline)
    P-->>W: Detailed Plot Draft
    loop Detailed Plot Discussion Rounds
        W->>C: review_detailed_plot(draft)
        C-->>W: Critique (Scene flow, Conflict intensity)
        W->>P: revise_detailed_plot(draft, critique)
        P-->>W: Final Detailed Plot Outline
    end
```
