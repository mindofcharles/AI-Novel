import logging
import os
import shutil
import sys
import tempfile
import json
import unittest
from unittest.mock import MagicMock

# Setup paths
CURRENT_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from autonomy.gated_reader import GatedFileReader
from autonomy.broker import MessageBroker
from autonomy.nodes import AgentNode
from autonomy.supervisor import SupervisorAgent
from workflow import WorkflowManager

class AIAutonomyDelegationTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = os.getcwd()
        self.tmpdir = tempfile.mkdtemp(prefix="ai_autonomy_test_")
        os.chdir(self.tmpdir)
        self.logger = logging.getLogger("autonomy-test")
        
        import config
        self.old_suite = getattr(config, "ENABLE_AUTONOMY_SUITE", False)
        self.old_budget = getattr(config, "ENABLE_BUDGET_MONITORING", False)
        config.ENABLE_AUTONOMY_SUITE = True
        config.ENABLE_BUDGET_MONITORING = True

    def tearDown(self):
        import config
        config.ENABLE_AUTONOMY_SUITE = self.old_suite
        config.ENABLE_BUDGET_MONITORING = self.old_budget
        
        os.chdir(self.old_cwd)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_gated_file_reader_large_file_outline(self):
        # 1. Create a dummy large file (60 KB)
        large_path = "large_log.txt"
        with open(large_path, "w", encoding="utf-8") as f:
            for i in range(1, 1500):
                f.write(f"This is log line number {i} containing some descriptive text data.\n")

        # Threshold 50 KB, Max chunk 100 lines
        reader = GatedFileReader(large_threshold_kb=50, max_chunk=100)

        # 2. Verify that reading without pagination returns the Outline Fallback
        outline = reader.read_file(large_path)
        self.assertIn("### LARGE FILE WARNING", outline)
        self.assertIn("Size", outline)
        self.assertIn("Total Lines", outline)
        self.assertIn("First 5 Lines Sample", outline)

        # 3. Read specific paginated chunk
        chunk = reader.read_file(large_path, start_line=10, end_line=15)
        self.assertNotIn("LARGE FILE WARNING", chunk)
        self.assertIn("10: This is log line number 10", chunk)
        self.assertIn("15: This is log line number 15", chunk)

        # 4. Test tail reading
        tail = reader.read_file_tail(large_path, line_count=5)
        self.assertIn("1499: This is log line number 1499", tail)

    def test_hierarchical_spawning_and_depth_limits(self):
        broker = MessageBroker()
        
        # Spawn Root node (Depth 0)
        root = AgentNode(name="Root", role="Root Planner", depth=0, parent=None, max_depth=2, broker=broker)
        
        # Spawn Child node (Depth 1)
        child = root.spawn_child(name="Child", role="Story Specialist")
        self.assertEqual(child.depth, 1)
        self.assertEqual(child.parent, root)
        self.assertIn(child, root.children)

        # Spawn Grandchild node (Depth 2)
        grandchild = child.spawn_child(name="Grandchild", role="Lore Research")
        self.assertEqual(grandchild.depth, 2)
        self.assertEqual(grandchild.parent, child)

        # Attempt to spawn Depth 3 (Should fail and escalate)
        with self.assertRaises(RuntimeError) as ctx:
            grandchild.spawn_child(name="GreatGrandchild", role="Fact Audit")
        
        self.assertIn("Depth limit exceeded", str(ctx.exception))

        # Check escalation message is in child's inbox
        self.assertEqual(len(child.message_inbox), 1)
        esc_msg = child.message_inbox[0]
        self.assertEqual(esc_msg["type"], "delegate_escalation")
        self.assertEqual(esc_msg["payload"]["request_type"], "spawn_subagent")
        self.assertEqual(esc_msg["payload"]["name"], "GreatGrandchild")

    def test_react_tool_invocation_loop(self):
        broker = MessageBroker()
        
        # Define mock tools
        sqlite_called = False
        def mock_query_sqlite(command: str) -> str:
            nonlocal sqlite_called
            sqlite_called = True
            return "[('Carol', 'dead')]"

        tools = {
            "query_sqlite": mock_query_sqlite
        }

        # Mock LLM client behaviour
        mock_llm = MagicMock()
        
        # Turn 1: Outputs tool action
        # Turn 2: Outputs final answer based on tool output
        mock_llm.generate.side_effect = [
            "Thought: I need to verify Carol's status.\nAction: {\"tool\": \"query_sqlite\", \"arguments\": {\"command\": \"SELECT name FROM characters\"}}",
            "Thought: I got the result. Carol is dead.\nFinal Answer: Character Carol is dead."
        ]

        node = AgentNode(
            name="Researcher",
            role="continuity",
            depth=0,
            llm_client=mock_llm,
            tools=tools,
            broker=broker
        )

        final_ans = node.execute_task("Find if Carol is dead.")
        self.assertEqual(final_ans, "Character Carol is dead.")
        self.assertTrue(sqlite_called)

    def test_supervisor_budget_termination(self):
        broker = MessageBroker()
        supervisor = SupervisorAgent(broker=broker, budget_limit_usd=0.05)

        # Setup dynamic mock node
        node = AgentNode(name="Auditee", role="Auditee", depth=0, broker=broker)

        # Send cost metrics through broker
        broker.send(
            sender="Auditee",
            recipient="OtherNode",
            msg_type="round_update",
            payload={"estimated_cost": 0.03}
        )
        self.assertEqual(len(node.message_inbox), 0) # No override yet

        # This send exceeds the limit (0.03 + 0.03 = 0.06 > 0.05)
        broker.send(
            sender="Auditee",
            recipient="Auditee",
            msg_type="round_update",
            payload={"estimated_cost": 0.03}
        )

        # Verify that supervisor intervened with EARLY_TERMINATION
        self.assertEqual(len(node.message_inbox), 2)
        msg = [m for m in node.message_inbox if m["type"] == "supervisor_intervention"][0]
        self.assertEqual(msg["payload"]["command"], "EARLY_TERMINATION")
        self.assertIn("exceeded limit", msg["payload"]["reason"])

    def test_supervisor_circular_logic_interjection(self):
        broker = MessageBroker()
        supervisor = SupervisorAgent(broker=broker, budget_limit_usd=1.00)

        node = AgentNode(name="Debater", role="Debater", depth=0, broker=broker)

        # Round 1, 2, 3 arguments that are highly circular (high word overlap)
        broker.send(
            sender="Critic",
            recipient="Debater",
            msg_type="debate_round_argument",
            payload={"argument": "Character Bob has died in chapter one. We cannot resurrect Bob without continuity breakdown. It violates the rules."}
        )
        broker.send(
            sender="Scanner",
            recipient="Debater",
            msg_type="debate_round_argument",
            payload={"argument": "Character Bob has died in chapter one. We cannot resurrect Bob without continuity breakdown. It violates the rules."}
        )
        
        # This round triggers circular interjection warning
        broker.send(
            sender="Critic",
            recipient="Debater",
            msg_type="debate_round_argument",
            payload={"argument": "Character Bob has died in chapter one. We cannot resurrect Bob without continuity breakdown. It violates the rules."}
        )

        # Verify supervisor triggers interjection prompt command
        self.assertEqual(len(node.message_inbox), 4)
        msg = [m for m in node.message_inbox if m["type"] == "supervisor_intervention"][0]
        self.assertEqual(msg["payload"]["command"], "INTERJECT_PROMPT")
        self.assertIn("Circular debate logic", msg["payload"]["reason"])

if __name__ == "__main__":
    unittest.main()
