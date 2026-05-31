import logging
from typing import Dict, List, Any, Optional

class SupervisorAgent:
    """
    Non-participating Observer agent that audits broker traffic,
    monitors narrative drift, polices resource cost limits, and
    performs control interjections on deadlock.
    """
    def __init__(self, broker: Any, budget_limit_usd: float = 1.00):
        self.broker = broker
        self.budget_limit_usd = budget_limit_usd
        self.accumulated_cost = 0.0
        self.discussion_history: List[dict] = []
        self.logger = logging.getLogger("SupervisorAgent")
        
        # Register self on broker
        self.broker.set_supervisor(self)

    def audit_message(self, sender: str, recipient: str, msg_type: str, payload: dict):
        """Asynchronously audits messages passing through the broker."""
        self.logger.info(f"Auditing message: {sender} -> {recipient} ({msg_type})")
        
        # Record discussion traffic
        self.discussion_history.append({
            "sender": sender,
            "recipient": recipient,
            "type": msg_type,
            "payload": payload
        })

        # 1. Audit Resource Cost Budget
        import config
        if getattr(config, "ENABLE_BUDGET_MONITORING", False):
            cost_estimate = payload.get("estimated_cost", 0.0)
            self.accumulated_cost += cost_estimate
            if self.accumulated_cost > self.budget_limit_usd:
                self.logger.warning(f"Supervisor Budget Limit Exceeded: ${self.accumulated_cost:.4f} > max ${self.budget_limit_usd}")
                self.trigger_intervention(
                    command="EARLY_TERMINATION",
                    target=recipient,
                    reason=f"Accumulated token cost ${self.accumulated_cost:.4f} exceeded limit ${self.budget_limit_usd}."
                )
                return

        # 2. Audit Circular Debate Deadlock
        if msg_type == "debate_round_argument":
            rounds = [d for d in self.discussion_history if d["type"] == "debate_round_argument"]
            if len(rounds) >= 3:
                # Basic lexical/overlap comparison on the last 3 debate turns to detect deadlock
                last_three = [r["payload"].get("argument", "") for r in rounds[-3:]]
                if self._detect_circular_logic(last_three):
                    self.logger.warning("Supervisor detected circular deadlock loop between debate agents!")
                    self.trigger_intervention(
                        command="INTERJECT_PROMPT",
                        target=recipient,
                        reason="Circular debate logic detected. Sibling agents are repeating identical continuity concerns. Force immediate compromise synthesis and close debate in the next turn."
                    )

    def trigger_intervention(self, command: str, target: str, reason: str):
        """Dispatches an overriding intervention command through the broker to nodes."""
        self.logger.warning(f"DISPATCHING SUPERVISOR INTERVENTION: command={command} target={target} reason={reason}")
        
        # Relays intervention
        self.broker.send(
            sender="Supervisor",
            recipient=target,
            msg_type="supervisor_intervention",
            payload={
                "command": command,
                "reason": reason
            }
        )

    def _detect_circular_logic(self, arguments: List[str]) -> bool:
        """Helper to analyze lexical overlap and detect circular repeating arguments."""
        if not arguments or len(arguments) < 3:
            return False
        
        # Clean and tokenize words
        token_sets = []
        for arg in arguments:
            words = set(str(arg).lower().replace(",", "").replace(".", "").replace("!", "").split())
            # filter short noise words
            filtered = {w for w in words if len(w) > 4}
            token_sets.append(filtered)

        # Check intersection overlap ratio between turns
        if not token_sets[0] or not token_sets[1] or not token_sets[2]:
            return False

        intersect_1_2 = token_sets[0].intersection(token_sets[1])
        intersect_2_3 = token_sets[1].intersection(token_sets[2])
        
        ratio_1_2 = len(intersect_1_2) / max(1, min(len(token_sets[0]), len(token_sets[1])))
        ratio_2_3 = len(intersect_2_3) / max(1, min(len(token_sets[1]), len(token_sets[2])))

        # If lexical overlap is very high (> 75%), flag as circular deadlock
        if ratio_1_2 > 0.75 and ratio_2_3 > 0.75:
            return True
        return False
