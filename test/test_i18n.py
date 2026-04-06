import os
import sys
import unittest

# Ensure src is in path
CURRENT_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import config
from workflow_components.resources import get_resource, get_res_num, is_chinese

class TestI18nLoading(unittest.TestCase):
    def test_chinese_loading(self):
        config.LANGUAGE = "Chinese"
        # Force re-init if needed (singleton reset for test)
        from workflow_components.resources import LanguageResources
        LanguageResources._instance = None
        
        self.assertTrue(is_chinese())
        self.assertEqual(get_resource("label.contract"), "写作契约")
        self.assertIn("设计世界设定集", get_resource("prompt.architect_task"))
        self.assertIn("必须全程仅使用中文输出", get_resource("prompt.language_rule"))
        
        # Test system prompts
        self.assertIn("架构师", get_resource("architect"))
        self.assertIn("叙事策划", get_resource("planner"))
        self.assertIn("正文的编写者", get_resource("writer"))
        
        # Test number
        self.assertEqual(get_res_num("lang.confidence_chinese_min"), 0.20)

    def test_english_loading(self):
        config.LANGUAGE = "English"
        from workflow_components.resources import LanguageResources
        LanguageResources._instance = None
        
        self.assertFalse(is_chinese())
        self.assertEqual(get_resource("label.contract"), "Writing Contract")
        self.assertIn("Design the World Bible", get_resource("prompt.architect_task"))
        
        # Test number
        self.assertEqual(get_res_num("lang.confidence_english_min"), 0.60)

if __name__ == "__main__":
    unittest.main()
