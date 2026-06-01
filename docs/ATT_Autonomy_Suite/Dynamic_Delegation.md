# Hierarchical Dynamic Delegation Specification

This document details the lifecycle, execution protocol, spawning gates, and safe ReAct tool parsing of the **Hierarchical Dynamic Delegation** framework under the ATT topology.

## 1. Dynamic Spawning & Lineage Hierarchy

Every autonomous task or research query spawns a specialized dynamic Agent Team (AT) inside a tree lineage structure coordinated by the `ATTManager`:

* **Level 0 (Root AI)**: The primary coordinating workflow agent (e.g. Root_AI_Level_0).
* **Level 1 (Child AT)**: Dynamic Agent Teams (enforcing size $N \ge 3$) spawned by Level 0 or its active members to manage specific domains (e.g., Chapter Planning Committee, World Bible Committee).
* **Level 2 (Grandchild AT)**: Dynamic sub-teams (size $N \ge 3$) recursively launched by Level 1 members to run micro-specialized validations (e.g., Timeline Integrity Auditor, DB Committee).

Both individual `Agent` instances and `AgentTeam` instances support dynamic spawning via the unified `launch_att()` method, maintaining complete structural equivalence across the tree lineage.

## 2. Bounded ReAct Execution Loop & Safe Parser

Agents in dynamic teams resolve tasks inside a structured **Reasoning & Action (ReAct)** loop. The loop alternates between `Thought`, `Action` (tool call), and `Observation` until a `Final Answer` is reached or the step limit is hit (default: 5).

### Prompt Sequence Protocol

1. **System Instruction**: Injects ReAct formatting instructions alongside the dynamic identity profile and the list of available tools:

   ```text
   Thought: Analyzing character status rules in database.
   Action: query_sqlite(SELECT status FROM characters WHERE name = 'Iris')
   Observation: [('dead',)]
   
   Thought: The character Iris is dead in the DB.
   Final Answer: Timeline conflict found: Iris is dead, contradiction exists.
   ```

2. **Safe Argument Parser**:
   To prevent parsing crashes when tools accept string arguments that contain commas (e.g., semantic search phrases or SQLite query arguments), the ReAct parser uses Python's safe literal evaluation (`ast.literal_eval`). This guarantees that string arguments with commas inside quotes are evaluated correctly as a single string parameter instead of being split incorrectly.

## 3. Bidirectional Escalation Channel

When an active team or agent at Level 2 determines that it needs further automated delegation or hits parent-routing gates:

1. It dispatches a structured escalation message upward to its parent team:

   ```json
   {
     "type": "escalation_spawn",
     "objective": "Task details to be delegated...",
     "rationale": "Objective details...",
     "from": "AT-abc123"
   }
   ```

2. The parent team receives this payload directly into its `message_inbox`.
3. During the parent team's next debate turn, the `ATTManager` automatically extracts these alerts and prepends them directly into the parent team's active discussion prompt.
4. Sibling agents in the parent team consume the alerts, formulate resolutions or delegate to a sibling node, and relay results back, maintaining flat execution bounds.

## 4. Consolidated Autonomy Tools

AIs are dynamically equipped with system-wide tools registered centrally in `tools.py`:

* **`query_sqlite(sql_command: str) -> str`**: Safe read queries audited by the Database Management Committee.
* **`search_faiss(query_text: str, limit: int = 3) -> str`**: Semantic searches over Tier 3 vector memory.
* **`read_file_chunk(path: str, start_line: int, end_line: int) -> str`**: Paginated gated file reads.
* **`read_file_tail(path: str, line_count: int) -> str`**: Last lines of logs/streams.
* **`dispatch_subagent(name: str, role: str, task: str) -> str`**: Spawns and executes a child dynamic subagent panel.
* **`delegate_escalation(objective: str, rationale: str) -> str`**: Escalates task objectives upward in the lineage tree.
* **`set_sibling_talk(child_id: str, allow: bool) -> str`**: Allows parent teams to dynamically authorize sibling peer communication.
