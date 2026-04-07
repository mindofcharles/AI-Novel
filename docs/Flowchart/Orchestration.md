# System Orchestration Flow

This document describes the high-level control flow of the AI Novel project, from initialization to continuous generation.

```mermaid
flowchart TD
    Start((Start CLI)) --> Init{--init?}
    Init -- Yes --> InitWorkspace[Initialize Workspace & Create Novel_Overview.md]
    InitWorkspace --> End((End))

    Init -- No --> StartProject{--start?}
    StartProject -- Yes --> LoadOverview[Load Novel_Overview.md]
    LoadOverview --> Architect[Architect Phase: World Bible & Discussion]
    Architect --> PlotOutline[Plot Phase: High-level & Detailed Outlines]
    PlotOutline --> SeedMemory[Seed Memory: Extract facts from Bible]
    SeedMemory --> AutoGen[Enter Chapter 1 Generation]
    AutoGen --> ChapterLoop

    StartProject -- No --> ChapterOp{--plan/--write/--scan?}
    ChapterOp -- Yes --> SingleOp[Execute Single Chapter Task]
    SingleOp --> End

    ChapterOp -- No --> AutoLoop{--auto?}
    AutoLoop -- Yes --> IntegrityCheck[Validate Runtime Artifacts & Integrity]
    IntegrityCheck --> ChapterLoop{{Chapter Generation Loop}}
    
    subgraph ChapterLoop [Chapter Generation Loop]
        direction TB
        C_Start[Start Chapter N] --> C_Integrity{Already Completed?}
        C_Integrity -- Yes --> C_Next[Skip to Chapter N+1]
        C_Integrity -- No --> C_Discard[Discard Incomplete Artifacts]
        C_Discard --> C_Plan[Planner: Generate Chapter Guide & Discussion]
        C_Plan --> C_Write[Writer: Write Chapter Text]
        C_Write --> C_Review[Critic: Review & Revise Chapter]
        C_Review --> C_Scan[Scanner: Extract Facts & Commit to Memory]
        C_Scan --> C_Next
    end
    
    C_Next --> LoopEnd{More Chapters?}
    LoopEnd -- Yes --> C_Start
    LoopEnd -- No --> End
```

## Sub-Flow Details

- [World Building & Framework](World_Building.md)
- [Chapter Generation Workflow](Chapter_Workflow.md)
- [Memory & Retrieval System](Memory_System.md)
- [Conflict & Integrity Management](Conflict_Management.md)
