# Flowchart

This document uses flowchart to describe the operational logic of each module in the entire project.

> [!NOTE]
> This document was largely written by AI and the content described at present is incomplete,
> so it is for reference only.

## 1. Project Initialization Phase (Architect ↔ Critic)

This phase establishes the "DNA" of the novel. The Architect proposes the world, and the Critic ensures it's robust enough for a long-form story.

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

Before any chapters are written, the Planner and Critic collaborate to define the "High-Level" and "Detailed" plot frames.

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

## 3. Chapter Planning Loop (Planner ↔ Critic ↔ Memory)

This sequence occurs for every chapter. The Planner acts as a "Contractor," defining what the Writer must deliver.

```mermaid
sequenceDiagram
    autonumber
    participant W as WorkflowManager
    participant M as Memory (StoryStateManager)
    participant P as Planner Agent
    participant C as Critic Agent

    W->>M: build_context_package(chapter_n)
    M->>M: 1. Intent Classification
    M->>M: 2. SQLite Retrieval (T1/T2 Facts)
    M->>M: 3. FAISS Retrieval (T3 Semantic Details)
    M->>M: 4. Cross-Tier Alignment (Check Contradictions)
    M-->>W: Aligned Context (Characters, Rules, History, Lore)

    W->>P: generate_chapter_guide(Context + Plot Frames)
    P-->>W: Chapter Guide Draft (The Writing Contract)

    loop Guide Discussion Rounds (config.CHAPTER_GUIDE_DISCUSSION_ROUNDS)
        W->>C: review_guide(draft, context)
        C-->>W: Critique (Actionability, Character consistency)
        W->>P: revise_guide(draft, critique)
        P-->>W: Revised Writing Contract
    end
    W->>W: Save Guide to novel/frame/chapter_guides/
```

## 4. Chapter Writing & Peer Review (Writer ↔ Critic ↔ Planner)

The Writer executes the "Contract" while the Critic ensures the output doesn't stray from the facts or the guide.

```mermaid
sequenceDiagram
    autonumber
    participant W as WorkflowManager
    participant P as Planner (The Contract)
    participant WR as Writer Agent
    participant C as Critic Agent

    W->>WR: write_chapter(Writing Contract + Memory Context)
    WR-->>W: Chapter Prose Draft

    loop Chapter Text Discussion Rounds (config.CHAPTER_REVISION_ROUNDS)
        W->>C: review_chapter_text(prose, contract, facts)
        Note right of C: Checks "Show, Don't Tell" & Logic
        C-->>W: Review (NEEDS_REVISION: Yes/No, Rationale, Patch)
        
        alt NEEDS_REVISION == Yes
            W->>WR: revise_chapter(prose, critique, contract)
            WR-->>W: Revised Prose
        else NEEDS_REVISION == No
            Note over W, WR: Proceed to Fact Archiving
        end
    end
    W->>W: Save Chapter to novel/main_text/chapters/
```

## 5. Fact Extraction & Memory Persistence (Scanner ↔ Memory)

The "Archivist" phase where narrative results are converted back into structured data for future chapters.

```mermaid
sequenceDiagram
    autonumber
    participant W as WorkflowManager
    participant S as Scanner Agent
    participant M as MemoryManager (SQLite + FAISS)
    participant CQ as Conflict Queue

    W->>S: scan_chapter(Final Chapter Text)
    S->>S: 1. Extract Entities & Status
    S->>S: 2. Extract Timeline Events
    S->>S: 3. Extract World Rule Updates
    S->>S: 4. Extract Tier-3 Semantic Details
    S-->>W: Structured Fact JSON Payload

    W->>M: begin_chapter_commit(Payload)
    M->>M: begin_batch (Atomic Transaction)
    
    M->>M: Logic Check: Resurrection? Identity Theft? Rule Breach?
    
    alt Logic Pass (No Conflicts)
        M->>M: upsert_characters / add_events / add_semantic
        M->>M: commit_batch
        M-->>W: Status: COMPLETED
    else Logic Fail (Conflicts Found)
        M->>CQ: queue_conflict(blocking_level, triage_metadata)
        M->>M: rollback_batch (Keep T1/T2 integrity)
        M-->>W: Status: FAILED (Blocked)
    end

    W->>W: Sync Compact Archives (Markdown snapshots)
```
