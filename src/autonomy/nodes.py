import json
import logging
from typing import Dict, List, Any, Optional

class AgentNode:
    """
    Represents an active, self-aware agent in the hierarchical dynamic delegation tree.
    Supports role-identity prompt injection and a bounded ReAct reasoning loop.
    """
    def __init__(
        self,
        name: str,
        role: str,
        depth: int,
        parent: Optional['AgentNode'] = None,
        max_depth: int = 2,
        llm_client: Optional[Any] = None,
        tools: Optional[Dict[str, Any]] = None,
        broker: Optional[Any] = None
    ):
        self.name = name
        self.role = role
        self.depth = depth
        self.parent = parent
        self.max_depth = max_depth
        self.llm_client = llm_client
        self.tools = tools or {}
        self.broker = broker
        
        self.children: List['AgentNode'] = []
        self.message_inbox: List[dict] = []
        self.active_objective: str = ""
        self.logger = logging.getLogger(f"AgentNode:{name}")

        # Register self on broker if available
        if self.broker:
            self.broker.register_node(self)

    def spawn_child(self, name: str, role: str, llm_client: Optional[Any] = None) -> 'AgentNode':
        """Spawns a child agent, enforcing strict depth limit (Max Depth = 2)."""
        if self.depth >= self.max_depth:
            self.logger.warning(f"Spawn blocked: Depth {self.depth} matches max depth limit. Escalating request.")
            
            # Escalation to parent
            if self.parent:
                escalation_payload = {
                    "request_type": "spawn_subagent",
                    "name": name,
                    "role": role,
                    "target": self.name
                }
                self.broker.send(
                    sender=self.name,
                    recipient=self.parent.name,
                    msg_type="delegate_escalation",
                    payload=escalation_payload
                )
            raise RuntimeError(f"Depth limit exceeded. Node '{self.name}' at depth {self.depth} cannot spawn child agents.")

        child = AgentNode(
            name=name,
            role=role,
            depth=self.depth + 1,
            parent=self,
            max_depth=self.max_depth,
            llm_client=llm_client or self.llm_client,
            tools=self.tools,
            broker=self.broker
        )
        self.children.append(child)
        return child

    def receive_message(self, message: dict):
        """Appends an incoming message to the node's inbox."""
        self.message_inbox.append(message)
        self.logger.info(f"Inbox update for '{self.name}': received message of type '{message.get('type')}' from '{message.get('from')}'.")

    def execute_task(self, task: str, max_steps: int = 5) -> str:
        """Runs the ReAct reasoning and tool invocation loop to solve the task."""
        self.active_objective = task
        self.logger.info(f"Starting task execution: '{task}' (Max ReAct Steps: {max_steps})")

        identity_header = self._build_identity_header()
        tools_description = self._build_tools_description()

        system_instruction = (
            f"You are a highly capable agent operating in a ReAct (Reasoning & Action) loop.\n"
            f"Solve the task using the tools provided below.\n\n"
            f"{identity_header}\n\n"
            f"## Available Tools:\n"
            f"{tools_description}\n\n"
            f"## Output Format Instructions:\n"
            f"For each step of your reasoning, you MUST output exactly one of the following two formats:\n\n"
            f"Format Option 1 (To execute a tool call):\n"
            f"Thought: Your current analytical reasoning.\n"
            f"Action: {{\"tool\": \"TOOL_NAME\", \"arguments\": {{\"key\": \"value\"}}}}\n\n"
            f"Format Option 2 (To provide your final answer):\n"
            f"Thought: Concluding reasoning.\n"
            f"Final Answer: Your final resolved output/report.\n\n"
            f"CRITICAL: Keep your 'Action:' payload as a single-line, strictly formatted, valid JSON block. "
            f"Never output conversational text or additional lines after an Action."
        )

        history = [f"Task: {task}"]
        
        for step in range(1, max_steps + 1):
            prompt = "\n".join(history) + f"\n\nStep {step}/{max_steps}:"
            
            # Call generation
            response = self.llm_client.generate(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=0.3
            ).strip()

            # Record turn
            history.append(response)

            # 1. Parse response for Action or Final Answer
            if "Final Answer:" in response:
                final_answer = response.split("Final Answer:", 1)[1].strip()
                self.logger.info("Task completed successfully: Final Answer found.")
                return final_answer
            
            if "Action:" in response:
                try:
                    action_line = response.split("Action:", 1)[1].strip()
                    # Clean markdown formatting if LLM wrapped in backticks
                    if action_line.startswith("```"):
                        action_line = action_line.replace("```json", "").replace("```", "").strip()
                    
                    action_data = json.loads(action_line)
                    tool_name = action_data.get("tool")
                    args = action_data.get("arguments", {})
                    
                    self.logger.info(f"ReAct Loop Step {step}: Invoking tool '{tool_name}' with args {args}")
                    
                    # Execute tool
                    observation = self._invoke_tool(tool_name, args)
                    history.append(f"Observation: {observation}")
                except Exception as e:
                    self.logger.error(f"Error parsing or executing ReAct tool call: {e}")
                    history.append(f"Observation: Error executing tool call: {e}")
            else:
                self.logger.warning("Agent output formatted incorrectly. Forcing next step.")
                history.append("Observation: Error: Output must start with either 'Action:' or 'Final Answer:'.")

        # Cap limit hit
        self.logger.warning("ReAct Loop step limit reached. Returning fallback.")
        return "Error: ReAct execution loop timed out before a Final Answer was reached."

    def _build_identity_header(self) -> str:
        parent_name = self.parent.name if self.parent else "None"
        peers = ", ".join([c.name for c in self.parent.children if c.name != self.name]) if self.parent else "None"
        spawn_block = " [SPAWNING BLOCKED]" if self.depth >= self.max_depth else ""
        
        return (
            f"## AGENT IDENTITY PROFILE\n"
            f"- **Role Name**: {self.role}\n"
            f"- **Agent Node Name**: {self.name}\n"
            f"- **Parent Agent**: {parent_name}\n"
            f"- **Active Sibling Peers**: {peers}\n"
            f"- **Depth Level**: {self.depth} / {self.max_depth}{spawn_block}\n"
            f"- **Current Objective**: {self.active_objective}"
        )

    def _build_tools_description(self) -> str:
        docs = []
        for name, func in self.tools.items():
            docs.append(f"- **{name}**: {func.__doc__ or 'No docstring provided.'}")
        return "\n".join(docs) if docs else "No tools available."

    def _invoke_tool(self, name: str, args: dict) -> str:
        if name not in self.tools:
            return f"Error: Tool '{name}' is not registered or available to this agent."
        
        try:
            # Inject estimated cost if broker tracks usage
            cost_estimate = 0.002
            if self.broker and self.broker.supervisor:
                self.broker.send(
                    sender=self.name,
                    recipient="Supervisor",
                    msg_type="token_cost_audit",
                    payload={"estimated_cost": cost_estimate}
                )

            return str(self.tools[name](**args))
        except Exception as e:
            return f"Error executing tool '{name}': {e}"
