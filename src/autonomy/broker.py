import logging
from typing import Dict, List, Any, Optional

class MessageBroker:
    """
    Coordinates and routes message transfers between parent, child,
    and sibling (peer) agents. Integrates with the SupervisorAgent to audit traffic.
    """
    def __init__(self):
        self.registry: Dict[str, Any] = {}
        self.supervisor: Optional[Any] = None
        self.logger = logging.getLogger("MessageBroker")

    def register_node(self, node: Any):
        """Registers an active AgentNode on the broker."""
        self.registry[node.name] = node
        self.logger.info(f"Registered AgentNode '{node.name}' (role: {node.role}) on broker.")

    def set_supervisor(self, supervisor: Any):
        """Registers the SupervisorAgent to audit message flow."""
        self.supervisor = supervisor
        self.logger.info("SupervisorAgent registered on broker.")

    def send(self, sender: str, recipient: str, msg_type: str, payload: dict):
        """Routes a message from sender to recipient."""
        # 1. Supervisor audits the traffic first if registered
        if self.supervisor and sender != "Supervisor":
            try:
                self.supervisor.audit_message(sender, recipient, msg_type, payload)
            except Exception as e:
                self.logger.error(f"Supervisor auditing error: {e}")

        # 2. Route the message to target node
        if recipient in self.registry:
            self.registry[recipient].receive_message({
                "from": sender,
                "type": msg_type,
                "payload": payload
            })
        else:
            self.logger.warning(f"Message routing failed: Recipient node '{recipient}' is not registered.")
