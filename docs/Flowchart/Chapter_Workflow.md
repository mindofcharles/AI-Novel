# Chapter Generation Workflow

This document details the iterative process of planning, writing, and scanning, including the automated "Guard" systems.

## 1. Chapter Planning Loop (Planner ↔ Critic ↔ Memory)

```mermaid
sequenceDiagram
    autonumber
    participant W as WorkflowManager
    participant M as Memory (Funnel)
    participant P as Planner
    participant C as Critic

    W->>M: build_context_package(chapter_n)
    M-->>W: Aligned Context (Rules + Chars + History)

    W->>P: generate_chapter_guide(Context + Plot Frames)
    P-->>W: Draft (Markdown)

    loop Guide Discussion (config.CHAPTER_GUIDE_DISCUSSION_ROUNDS)
        W->>C: review_guide(draft)
        C-->>W: Critique
        W->>P: revise_guide(draft, critique)
        P-->>W: Revised Guide
    end
    W->>W: Save chapter_n_guide.md
```

## 2. Chapter Writing & Language Guard

Every output from an LLM agent is passed through a language validator before being accepted.

```mermaid
flowchart TD
    Write[Writer: Generate Prose] --> Guard{_enforce_output_language}
    
    Guard -- "Confidence >= Threshold (CJK vs Latin)" --> Accept[Accept Prose]
    
    Guard -- "Confidence < Threshold" --> Rewrite[Log Warning: Language Guard Triggered]
    Rewrite --> LLM_Rewrite[LLM: Specialized Rewrite Task]
    LLM_Rewrite -- "Keep structure, translate to Target Language" --> Accept
    
    Accept --> Save[Save chapter_n.md]
    Save --> Review[Critic: Review & Revise Chapter]
```

## 3. Review, Scan & Commit

The final stage ensures the written text is converted back into facts and committed to memory.

```mermaid
flowchart TD
    Review[Critic Review] --> NeedsRev{Needs Revision?}
    NeedsRev -- Yes --> Writer[Writer: Apply Patch]
    Writer --> Review
    
    NeedsRev -- No --> Scan[Scanner: Extract Facts]
    Scan --> Commit{Memory: Chapter Commit}
    
    Commit -- COMPLETED --> End((Next Chapter))
    
    Commit -- FAILED --> FailedCommit[Record in failed_commits table]
    FailedCommit --> User[User Resolution Required]
    
    User -- "--replay-commit ID" --> Replay[WorkflowManager: Replay Logic]
    Replay --> Commit
```
