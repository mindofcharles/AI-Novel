import os
import logging
from typing import Dict, Any, Optional, Callable, List, Tuple

import config

logger = logging.getLogger("ATT.Tools")

class Tool:
    """Encapsulates an AI tool with name, description, and execution logic."""
    def __init__(self, name: str, description: str, func: Callable[..., Any]):
        self.name = name
        self.description = description
        self.func = func

    def __call__(self, *args, **kwargs) -> str:
        try:
            res = self.func(*args, **kwargs)
            return str(res)
        except Exception as e:
            logger.error(f"Error executing tool '{self.name}': {e}")
            return f"Error executing tool '{self.name}': {e}"


def get_default_tools(context: Dict[str, Any], caller_node: Any) -> Dict[str, Tool]:
    """
    Centralized factory that registers and returns the default set of autonomy tools.
    
    Context dictionary requires:
      - 'memory': MemoryManager (for query_sqlite, search_faiss)
      - 'embedding_client': LLMClient (for search_faiss)
      - 'gated_reader': GatedFileReader (for file reads)
      - 'att_manager': ATTManager (for dynamic spawning and escalations)
      - 'db_committee': DatabaseManagementCommittee (for transaction safety auditing)
    """
    memory = context.get("memory")
    embedding_client = context.get("embedding_client")
    gated_reader = context.get("gated_reader")
    att_manager = context.get("att_manager")
    db_committee = context.get("db_committee")

    def query_sqlite(sql_command: str) -> str:
        """Queries the SQLite database directly. Arguments: sql_command (str)"""
        if db_committee:
            approved, reason = db_committee.audit_query(sql_command)
            if not approved:
                return f"Error: Database Management Committee rejected this query: {reason}"
        if not memory:
            return "Error: Database memory manager is not available in tools context."
        try:
            memory.cursor.execute(sql_command)
            rows = memory.cursor.fetchall()
            return str(rows)
        except Exception as e:
            return f"SQLite Error: {e}"

    def search_faiss(query_text: str, limit: int = 3) -> str:
        """Performs semantic vector search on FAISS indices. Arguments: query_text (str), limit (int)"""
        if not embedding_client:
            return "Error: Embedding client not available in tools context."
        if not memory:
            return "Error: Database memory manager is not available in tools context."
        try:
            emb = embedding_client.get_embedding(query_text)
            if not emb:
                return "Error: Could not generate embedding."
            hits = memory.search_semantic(emb, k=int(limit))
            return str(hits)
        except Exception as e:
            return f"FAISS Search Error: {e}"

    def read_file_chunk(path: str, start_line: int = 1, end_line: Optional[int] = None) -> str:
        """Reads a specific paginated chunk of a file. Arguments: path (str), start_line (int), end_line (int)"""
        if not gated_reader:
            return "Error: GatedFileReader not available in tools context."
        try:
            start_line = int(start_line)
            if end_line is not None:
                end_line = int(end_line)
            return gated_reader.read_file(path, start_line, end_line)
        except Exception as e:
            return f"Error reading file chunk: {e}"

    def read_file_tail(path: str, line_count: int = 50) -> str:
        """Reads the last line_count lines of a file or log. Arguments: path (str), line_count (int)"""
        if not gated_reader:
            return "Error: GatedFileReader not available in tools context."
        try:
            line_count = int(line_count)
            return gated_reader.read_file_tail(path, line_count)
        except Exception as e:
            return f"Error reading file tail: {e}"

    def dispatch_subagent(task: str, team_purpose: str, member_count: int = 3, roles_and_models: Optional[Dict[str, str]] = None, system_instructions: str = "") -> str:
        """Spawns a recursive child AT under the ATT tree to execute a specialized task. Arguments: task (str), team_purpose (str), member_count (int), roles_and_models (dict), system_instructions (str)"""
        if not getattr(config, "ENABLE_DYNAMIC_DELEGATION", False):
            return "Error: Dynamic Subagent Delegation is disabled in config."
        if not att_manager:
            return "Error: ATTManager not available in tools context."
        
        from att.att_core import Agent, AgentTeam
        actual_team = None
        if isinstance(caller_node, AgentTeam):
            actual_team = caller_node
        elif isinstance(caller_node, Agent):
            for team in att_manager.teams.values():
                if caller_node in team.members:
                    actual_team = team
                    break
        
        current_depth = actual_team.depth if actual_team else 1
        max_depth = getattr(config, "MAX_DELEGATION_DEPTH", 2)
        if current_depth >= max_depth:
            return f"Error: Cannot spawn child AT. Max delegation depth ({max_depth}) reached. You must use `delegate_escalation` to ask your parent for help."

        try:
            member_count = int(member_count)
            min_size = getattr(config, 'MIN_SUBAGENT_TEAM_SIZE', 3)
            if member_count < min_size:
                return f"Error: A valid Agent Team MUST have at least {min_size} members. Please reconsider your team design and try again."
        except ValueError:
            return "Error: member_count must be an integer."
        
        try:
            roles_and_presets = []
            if roles_and_models:
                for role_name, model_key in roles_and_models.items():
                    # Dynamic allocation. (In future, bind specific client based on model_key)
                    roles_and_presets.append((f"Dynamic_{role_name}", role_name))
            else:
                from att.presets import get_preset
                preset = get_preset("generic")
                roles_and_presets = preset["roles"]

            child_team = caller_node.launch_att(
                manager=att_manager,
                member_count=member_count,
                roles_and_presets=roles_and_presets,
                system_instructions=system_instructions,
                team_purpose=team_purpose
            )
            return att_manager.execute_team_discussion(child_team, task, rounds=getattr(config, "SUBAGENT_DISCUSSION_ROUNDS", 2))
        except Exception as e:
            return f"Dispatch Subagent Team Error: {e}"

    def delegate_escalation(objective: str, rationale: str) -> str:
        """Escalates objective upward in the ATT lineage tree. Arguments: objective (str), rationale (str)"""
        if not att_manager:
            return "Error: ATTManager not available in tools context."
        
        from att.att_core import Agent, AgentTeam
        actual_team = None
        if isinstance(caller_node, AgentTeam):
            actual_team = caller_node
        elif isinstance(caller_node, Agent):
            for team in att_manager.teams.values():
                if caller_node in team.members:
                    actual_team = team
                    break
        
        if not actual_team:
            return "Error: Could not resolve the active AgentTeam for the caller."

        parent = actual_team.parent_team or att_manager.find_parent_team(actual_team)
        if not parent:
            return "Error: No parent team exists to escalate to."
        
        try:
            payload = {
                "type": "escalation_spawn",
                "objective": objective,
                "rationale": rationale,
                "from": actual_team.team_id
            }
            parent.receive_message(payload)
            return f"Escalation successfully dispatched to parent team '{parent.team_id}'."
        except Exception as e:
            return f"Escalation Error: {e}"

    def set_sibling_talk(child_id: str, allow: bool = True) -> str:
        """Sets sibling talk permission for a child team. Arguments: child_id (str), allow (bool)"""
        if not att_manager:
            return "Error: ATTManager not available in tools context."
        
        if child_id not in att_manager.teams:
            return f"Error: Child team '{child_id}' is not registered."
            
        child = att_manager.teams[child_id]
        
        from att.att_core import Agent, AgentTeam
        actual_team = None
        if isinstance(caller_node, AgentTeam):
            actual_team = caller_node
        elif isinstance(caller_node, Agent):
            for team in att_manager.teams.values():
                if caller_node in team.members:
                    actual_team = team
                    break
                    
        if not actual_team:
            return "Error: Could not resolve the active AgentTeam for the caller."
            
        parent = child.parent_team or att_manager.find_parent_team(child)
        if not parent or parent.team_id != actual_team.team_id:
            return f"Error: Caller team '{actual_team.team_id}' is not the parent of child '{child_id}'."
            
        child.communication_rules["allow_sibling_talk"] = bool(allow)
        return f"Successfully set sibling talk for child team '{child_id}' to {allow}."

    def update_team_purpose(new_purpose: str) -> str:
        """Updates the purpose string of the caller's team. Arguments: new_purpose (str)"""
        from att.att_core import Agent, AgentTeam
        actual_team = None
        if isinstance(caller_node, AgentTeam):
            actual_team = caller_node
        elif isinstance(caller_node, Agent):
            for team in att_manager.teams.values():
                if caller_node in team.members:
                    actual_team = team
                    break
        if not actual_team:
            return "Error: Could not resolve the active AgentTeam."
        
        old_purpose = actual_team.team_purpose
        actual_team.team_purpose = new_purpose
        return f"Successfully updated team purpose from '{old_purpose}' to '{new_purpose}'."

    def send_peer_message(team_id: str, message: str) -> str:
        """Sends a message to the inbox of a peer team using their Team ID. Arguments: team_id (str), message (str)"""
        if not att_manager:
            return "Error: ATTManager not available."
        if team_id not in att_manager.teams:
            return f"Error: Team '{team_id}' not found."
            
        target = att_manager.teams[team_id]
        
        from att.att_core import Agent, AgentTeam
        actual_team = None
        if isinstance(caller_node, AgentTeam):
            actual_team = caller_node
        elif isinstance(caller_node, Agent):
            for team in att_manager.teams.values():
                if caller_node in team.members:
                    actual_team = team
                    break
                    
        sender_id = actual_team.team_id if actual_team else "Unknown"
        target.receive_message({
            "type": "peer_message",
            "from": sender_id,
            "objective": message
        })
        return f"Message successfully delivered to team '{team_id}'."

    return {
        "query_sqlite": Tool("query_sqlite", "Queries the SQLite database directly with sql_command (str).", query_sqlite),
        "search_faiss": Tool("search_faiss", "Performs semantic vector search on FAISS indices using query_text (str) and limit (int).", search_faiss),
        "read_file_chunk": Tool("read_file_chunk", "Reads a specific paginated chunk of a file using path (str), start_line (int), and optionally end_line (int).", read_file_chunk),
        "read_file_tail": Tool("read_file_tail", "Reads the last line_count (int) lines of a file using path (str).", read_file_tail),
        "dispatch_subagent": Tool("dispatch_subagent", "Spawns a child AT. Arguments: task (str), team_purpose (str), member_count (int), roles_and_models (dict), system_instructions (str).", dispatch_subagent),
        "delegate_escalation": Tool("delegate_escalation", "Escalates objective upward in the ATT lineage tree with objective (str) and rationale (str).", delegate_escalation),
        "set_sibling_talk": Tool("set_sibling_talk", "Allows parent teams to dynamically set sibling communication permission for their child team. Arguments: child_id (str), allow (bool).", set_sibling_talk),
        "update_team_purpose": Tool("update_team_purpose", "Updates the purpose string of the caller's team. Arguments: new_purpose (str)", update_team_purpose),
        "send_peer_message": Tool("send_peer_message", "Sends a message to a peer team's inbox using their Team ID. Arguments: team_id (str), message (str)", send_peer_message)
    }
