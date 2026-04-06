import json
import os
import re
from typing import Dict, Any, List

import config

class LanguageResources:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LanguageResources, cls).__new__(cls)
            cls._instance._init_resources()
        return cls._instance

    def _init_resources(self):
        # Default to zh-CN if configuration is "Chinese", otherwise "en"
        # We can map more complex names if needed.
        self.language_code = "zh-CN" if config.LANGUAGE == "Chinese" else "en"
        self.is_chinese = (config.LANGUAGE == "Chinese")
        self.resources: Dict[str, Any] = {}
        
        # Load from i18n directory
        # The i18n directory is in the project root
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        i18n_root = os.path.join(project_root, "i18n")
        
        # 1. Load messages (UI/Human)
        ui_path = os.path.join(i18n_root, "messages", self.language_code, "ui.json")
        self._load_json(ui_path)
        
        # 2. Load AI fragments
        ai_fragments_path = os.path.join(i18n_root, "AI", self.language_code, "fragments.json")
        self._load_json(ai_fragments_path)
        
        # 3. Load AI templates (Markdown)
        ai_templates_path = os.path.join(i18n_root, "AI", self.language_code, "templates.md")
        self._load_markdown_templates(ai_templates_path)

    def _load_json(self, path: str):
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.resources.update(data)
        except Exception:
            pass

    def _load_markdown_templates(self, path: str):
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            sections = re.split(r"^##\s+", content, flags=re.MULTILINE)
            for section in sections:
                lines = section.strip().split("\n")
                if not lines:
                    continue
                header = lines[0].strip()
                body = "\n".join(lines[1:]).strip()
                if header:
                    self.resources[header] = body
        except Exception:
            pass

    def get(self, key: str, **kwargs) -> str:
        text = self.resources.get(key, f"MISSING_RESOURCE_{key}")
        if kwargs:
            try:
                return text.format(**kwargs)
            except KeyError as e:
                return f"RESOURCE_FORMAT_ERROR_{key}_{e}"
        return text

    def get_num(self, key: str) -> float:
        val = self.resources.get(key, 0.0)
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    def get_all(self, keys: List[str]) -> Dict[str, str]:
        return {k: self.get(k) for k in keys}

def get_resource(key: str, **kwargs) -> str:
    return LanguageResources().get(key, **kwargs)

def get_res_num(key: str) -> float:
    return LanguageResources().get_num(key)

def is_chinese() -> bool:
    return LanguageResources().is_chinese
