import logging
from typing import Dict, Any, Optional

import config
from autonomy.gated_reader import GatedFileReader
from autonomy.broker import MessageBroker
from autonomy.nodes import AgentNode
from autonomy.supervisor import SupervisorAgent

class AutonomyWorkflowMixin:
    """
    Mixin integrating GatedFileReader, MessageBroker, AgentNode, and SupervisorAgent
    into the WorkflowManager, providing a ReAct tool invocation broker at runtime.
    """
    def initialize_autonomy(self):
        """Initializes the autonomy modules, including broker, reader, and supervisor."""
        if not getattr(config, "ENABLE_AUTONOMY_SUITE", False):
            self.gated_reader = None
            self.broker = None
            self.supervisor = None
            return

        self.gated_reader = GatedFileReader(
            large_threshold_kb=getattr(config, "LARGE_FILE_THRESHOLD_KB", 50),
            max_chunk=getattr(config, "MAX_CHUNK_LINES", 100)
        )
        self.broker = MessageBroker()
        
        # Spawn supervisor to audit message transfers
        self.supervisor = SupervisorAgent(
            broker=self.broker,
            budget_limit_usd=getattr(config, "TOTAL_TOKEN_BUDGET_USD", 1.00)
        )

    def get_autonomy_tools(self, caller_node: Any) -> Dict[str, Any]:
        """Assembles the tools map bound to a specific AgentNode."""
        
        def query_sqlite(sql_command: str) -> str:
            """Queries the SQLite database directly. Arguments: sql_command (str)"""
            try:
                self.memory.cursor.execute(sql_command)
                rows = self.memory.cursor.fetchall()
                return str(rows)
            except Exception as e:
                return f"SQLite Error: {e}"

        def search_faiss(query_text: str, limit: int = 3) -> str:
            """Performs semantic vector search on FAISS indices. Arguments: query_text (str), limit (int)"""
            try:
                emb = self.embedding_client.get_embedding(query_text)
                if not emb:
                    return "Error: Could not generate embedding."
                hits = self.memory.search_semantic(emb, k=limit)
                return str(hits)
            except Exception as e:
                return f"FAISS Search Error: {e}"

        def read_file_chunk(path: str, start_line: int = 1, end_line: Optional[int] = None) -> str:
            """Reads a specific paginated chunk of a file. Arguments: path (str), start_line (int), end_line (int)"""
            return self.gated_reader.read_file(path, start_line, end_line)

        def read_file_tail(path: str, line_count: int = 50) -> str:
            """Reads the last line_count lines of a file or log. Arguments: path (str), line_count (int)"""
            return self.gated_reader.read_file_tail(path, line_count)

        def dispatch_subagent(name: str, role: str, task: str) -> str:
            """Spawns a child subagent to execute a specialized research task. Arguments: name (str), role (str), task (str)"""
            if not getattr(config, "ENABLE_DYNAMIC_DELEGATION", False):
                return "Error: Dynamic Subagent Delegation is disabled in config."
            
            try:
                child = caller_node.spawn_child(name, role)
                # Bind tools to the new child
                child.tools = self.get_autonomy_tools(child)
                return child.execute_task(task)
            except Exception as e:
                return f"Dispatch Subagent Error: {e}"

        def delegate_escalation(objective: str, rationale: str) -> str:
            """(For Depth 2 Grandchildren) Escalates objective upward to parent. Arguments: objective (str), rationale (str)"""
            if not caller_node.parent:
                return "Error: No parent node exists to escalate to."
            
            try:
                payload = {
                    "request_type": "escalation_spawn",
                    "objective": objective,
                    "rationale": rationale,
                    "target": caller_node.name
                }
                self.broker.send(
                    sender=caller_node.name,
                    recipient=caller_node.parent.name,
                    msg_type="delegate_escalation",
                    payload=payload
                )
                return f"Escalation successfully dispatched to parent '{caller_node.parent.name}'."
            except Exception as e:
                return f"Escalation Error: {e}"

        return {
            "query_sqlite": query_sqlite,
            "search_faiss": search_faiss,
            "read_file_chunk": read_file_chunk,
            "read_file_tail": read_file_tail,
            "dispatch_subagent": dispatch_subagent,
            "delegate_escalation": delegate_escalation
        }

    def spawn_root_agent(self, name: str, role: str, llm_client: Any) -> Any:
        """Spawns the root (depth 0) agent Node."""
        root = AgentNode(
            name=name,
            role=role,
            depth=0,
            parent=None,
            max_depth=getattr(config, "MAX_DELEGATION_DEPTH", 2),
            llm_client=llm_client,
            tools=None, # will bind next
            broker=self.broker
        )
        root.tools = self.get_autonomy_tools(root)
        return root
