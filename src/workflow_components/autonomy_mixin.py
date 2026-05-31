import logging
from typing import Dict, Any, Optional, Tuple

import config
from att.att_core import ATTManager
from att.db_committee import DatabaseManagementCommittee
from autonomy.gated_reader import GatedFileReader

class AutonomyWorkflowMixin:
    """
    Mixin integrating ATTManager and DatabaseManagementCommittee
    into the WorkflowManager, providing the new AI Team Team (ATT)
    topology routing and tool execution.
    """
    def initialize_autonomy(self):
        """Initializes the ATT core manager, gated reader, and DB committee."""
        self.gated_reader = GatedFileReader(
            large_threshold_kb=getattr(config, "LARGE_FILE_THRESHOLD_KB", 50),
            max_chunk=getattr(config, "MAX_CHUNK_LINES", 100)
        )
        
        # Instantiate the unified ATTManager
        # Root AI represents the level 0 root node (Architect/Default)
        from att.att_core import Agent
        root_agent = Agent(name="Root_AI_Level_0", role="Architect", llm_client=self.critic_client)
        self.att_manager = ATTManager(root_ai=root_agent, critic_client=self.critic_client)
        
        # Establish the 3-AI Database Management Committee
        self.db_committee = DatabaseManagementCommittee(self.att_manager)
        
        # Register the Database Management Committee on MemoryManager
        self.memory.set_db_committee(self.db_committee)

        # Register the centralized tools context
        self.att_manager.register_tools_context({
            "memory": self.memory,
            "embedding_client": self.embedding_client,
            "gated_reader": self.gated_reader,
            "att_manager": self.att_manager,
            "db_committee": self.db_committee
        })

    def get_autonomy_tools(self, caller_node: Any) -> Dict[str, Any]:
        """Assembles the tools map bound to a specific AgentTeam or Member."""
        from att.tools import get_default_tools
        context = {
            "memory": self.memory,
            "embedding_client": self.embedding_client,
            "gated_reader": self.gated_reader,
            "att_manager": self.att_manager,
            "db_committee": self.db_committee
        }
        return get_default_tools(context, caller_node)
