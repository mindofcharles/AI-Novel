import logging
import os
import shutil
import sys
import tempfile
import unittest

# Setup paths
CURRENT_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from autonomy.gated_reader import GatedFileReader

class AIAutonomyDelegationTests(unittest.TestCase):
    def setUp(self):
        self.old_cwd = os.getcwd()
        self.tmpdir = tempfile.mkdtemp(prefix="ai_autonomy_test_")
        os.chdir(self.tmpdir)
        self.logger = logging.getLogger("autonomy-test")

    def tearDown(self):
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

if __name__ == "__main__":
    unittest.main()
