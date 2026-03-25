import logging
import os
import shutil
import sys
import tempfile
import unittest

CURRENT_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from workflow import WorkflowManager


class ProjectLogicSplitInitStartTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = os.getcwd()
        self.tmpdir = tempfile.mkdtemp(prefix="ai_novel_project_logic_")
        os.chdir(self.tmpdir)

        wf = WorkflowManager.__new__(WorkflowManager)
        wf.logger = logging.getLogger("project-logic-test")
        wf.world_dir = os.path.join("novel", "frame", "world")
        wf.plot_dir = os.path.join("novel", "frame", "plot")
        wf.guides_dir = os.path.join("novel", "frame", "chapter_guides")
        wf.archives_dir = os.path.join("novel", "frame", "archives")
        wf.chapters_dir = os.path.join("novel", "main_text", "chapters")
        wf.critiques_dir = os.path.join("novel", "process", "critiques")
        wf.discussions_dir = os.path.join("novel", "process", "discussions")
        wf.facts_dir = os.path.join("novel", "process", "facts")
        wf.reviews_dir = os.path.join("novel", "process", "reviews")
        wf.revisions_dir = os.path.join("novel", "process", "revisions")
        wf.discussion_log_dir = os.path.join("novel", "Discussion_Log")
        self.wf = wf

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_init_creates_overview_template(self):
        overview_path = self.wf.initialize_novel_workspace()
        self.assertTrue(os.path.exists(overview_path))
        with open(overview_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("This file should contain only your requirements", content)
        self.assertTrue(os.path.exists(os.path.join("novel", "Discussion_Log")))
        self.assertTrue(os.path.exists(os.path.join("novel", "Discussion_Log", "All_Discussion.log")))
        self.assertTrue(
            os.path.exists(
                os.path.join("novel", "Discussion_Log", "Novel_World_building_Discussion.log")
            )
        )

    def test_load_overview_rejects_unfilled_template(self):
        self.wf.initialize_novel_workspace()
        with self.assertRaises(RuntimeError):
            self.wf.load_novel_overview()

    def test_load_overview_returns_user_content(self):
        overview_path = self.wf.initialize_novel_workspace()
        with open(overview_path, "w", encoding="utf-8") as f:
            f.write("# Novel Overview\n\nA romance story in a rainy coastal city.")
        loaded = self.wf.load_novel_overview()
        self.assertIn("romance story", loaded)

    def test_discussion_log_keeps_full_detail_and_clear_separator(self):
        self.wf.initialize_novel_workspace()
        text = "line1\nline2\n\nline4"
        self.wf._append_discussion_log(
            title="Test Entry",
            content=text,
            chapter_num=1,
            world_building=True,
        )
        all_path = os.path.join("novel", "Discussion_Log", "All_Discussion.log")
        with open(all_path, "r", encoding="utf-8") as f:
            log_content = f.read()
        self.assertIn("ENTRY_ID:", log_content)
        self.assertIn("TITLE: Test Entry", log_content)
        self.assertIn("line1\nline2\n\nline4", log_content)
        self.assertIn("=" * 108, log_content)


if __name__ == "__main__":
    unittest.main()
