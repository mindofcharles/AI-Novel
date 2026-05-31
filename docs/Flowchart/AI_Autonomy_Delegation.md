# AI Autonomy & Subagent Delegation Flow

This document details the architectural layout, flowcharts, and operational logic of the **High-Level AI Autonomy, Hierarchical Dynamic Subagent Delegation, and Supervisor Auditor Agent** suite.

---

## 1. Multi-Agent Delegation Tree (Spawning Limits)

To prevent run-away recursive agent loops, spawning is strictly gated at a maximum depth of 2 (Root = Depth 0, Child = Depth 1, Grandchild = Depth 2). Any further spawning requests by a Grandchild are intercepted and escalated back up to the Child node as structured JSON messages.

```mermaid
flowchart TD
    Root["Root Agent Node\n(Depth 0: Writer / Planner)"] -->|Spawns| Child["Child Agent Node\n(Depth 1: Backstory Researcher)"]
    Child -->|Spawns| Grandchild["Grandchild Agent Node\n(Depth 2: MBTI Auditor)"]
    
    Grandchild -->|Try to Spawn| GrandchildSpawn{"Spawn Subagent?"}
    GrandchildSpawn -- "Yes (Blocked)" --> Escalate["Escalate structured JSON\nrequest to Child (Depth 1)"]
    Escalate --> ParentAction{"Parent (Child Node)\napproves & executes?"}
    ParentAction -- "Yes" --> SiblingSpawn["Parent spawns sibling agent\nto run task, then returns result"]
    ParentAction -- "No" --> Reject["Escalation request rejected\n& returns error/fallback"]
    
    GrandchildSpawn -- "No" --> DirectExecute["Execute direct ReAct tools"]
```

---

## 2. Gated File Reader (Context Protection Window)

To protect the LLM context window from massive logs or data dumps, direct reading of large files is dynamically blocked based on size. Large files must be queried selectively using paginated slice-reads.

```mermaid
flowchart TD
    Req["Read File Request (Path)"] --> SizeCheck{"File Size > Threshold?\n(default: 50 KB)"}
    
    SizeCheck -- "Yes" --> EndLineCheck{"Specific slice requested?\n(end_line is provided)"}
    
    EndLineCheck -- "No" --> OutlineFallback["1. Count total lines\n2. Extract first 5 lines sample\n3. Return structured Outline Warning"]
    EndLineCheck -- "Yes" --> SlicePaginate["Paginate lines\n[start_line to end_line]\nCapped at max_chunk_lines (100)"]
    
    SizeCheck -- "No" --> StdRead["Read whole file\n(Capped at max_chunk_lines if no end_line)"]
    
    OutlineFallback --> Response["Return to Agent Node"]
    SlicePaginate --> Response
    StdRead --> Response
```

---

## 3. Communication & Message Routing Broker

Agents communicate via a centralized `MessageBroker`. Sibling peer nodes can collaborate on shared topics, while all messages are routed asynchronously through the broker to allow continuous audits.

```mermaid
sequenceDiagram
    autonumber
    actor Parent as Parent Agent (Depth N-1)
    actor Child1 as Sibling Node A (Depth N)
    actor Child2 as Sibling Node B (Depth N)
    participant Broker as Message Broker
    participant Supervisor as Supervisor Agent (Auditor)

    Parent->>Broker: Spawn Node A & Node B (Register)
    Broker->>Child1: Registered
    Broker->>Child2: Registered
    
    Note over Child1, Child2: Peer-to-Peer Collaborative Debate
    
    Child1->>Broker: Send message to Sibling Node B
    activate Broker
    Broker->>Supervisor: Audit Traffic (sender != 'Supervisor')
    activate Supervisor
    Note over Supervisor: Checks Cost Budget & Circular deadlocks
    Supervisor-->>Broker: Audit approved
    deactivate Supervisor
    Broker->>Child2: Deliver inbox message payload
    deactivate Broker
```

---

## 4. Supervisor Agent Intervention Loop

The **Supervisor Agent** operates as an asynchronous, non-participating observer. It subscribes to the `MessageBroker` and intercepts traffic, keeping track of total session costs and analyzing discussions for circular arguments.

```mermaid
flowchart TD
    Msg["Incoming Broker Message\n(Sender, Recipient, Payload)"] --> SaveHist["1. Append to Discussion History"]
    
    SaveHist --> BudgetCheck{"2. Budget Monitoring Enabled?"}
    
    BudgetCheck -- "Yes" --> AddCost["Accumulate estimated cost"]
    AddCost --> LimitExceed{"Accumulated Cost > Limit?\n(default: $1.00)"}
    LimitExceed -- "Yes" --> EarlyTerm["Dispatch intervention:\nEARLY_TERMINATION"]
    LimitExceed -- "No" --> LoopCheck
    
    BudgetCheck -- "No" --> LoopCheck{"3. Message Type == 'debate_round_argument'?"}
    
    LoopCheck -- "Yes" --> WindowCheck{"Last 3 debate arguments present?"}
    WindowCheck -- "Yes" --> DeadlockCheck{"Analyze lexical overlap ratio\nbetween turns (> 75%)"}
    
    DeadlockCheck -- "Circular Deadlock" --> Interject["Dispatch intervention:\nINTERJECT_PROMPT\n(Force Planner to compromise)"]
    DeadlockCheck -- "Normal discussion" --> Pass["Pass message through to recipient"]
    
    LoopCheck -- "No" --> Pass
    WindowCheck -- "No" --> Pass
    EarlyTerm --> HaltNode["Terminate Node thread & fail-fast"]
    Interject --> PlannerOverride["Planner receives override instructions"]
```

---

## 5. Summary of Supervisor Intervention Commands

| Command | Triggers | Action Taken |
| :--- | :--- | :--- |
| **`INTERJECT_PROMPT`** | Circular lexical repetition detected across a 3-turn debate sliding window. | Injects strict override prompt to force the Planner to synthesize a compromise immediately on the next turn. |
| **`EARLY_TERMINATION`** | Total accumulated session cost exceeds budget cap (e.g. `$1.00`). | Shuts down the team execution, aborting the active transaction and triggering a fail-fast standby. |
| **`PRUNE_NODE`** | Subagent has finished its assigned research task. | Safely shuts down the child node, frees allocated memory, and cleans up active DB connections. |
