import os
import re
from typing import Dict


def load_system_prompts(language: str, src_dir: str) -> Dict[str, str]:
    lang_code = "zh" if language == "Chinese" else "en"
    prompts_file = os.path.join(src_dir, "prompts", f"{lang_code}.md")

    try:
        with open(prompts_file, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError as exc:
        raise RuntimeError(f"Prompt file not found: {prompts_file}") from exc

    prompts: Dict[str, str] = {}
    sections = re.split(r"^##\s+", content, flags=re.MULTILINE)
    for section in sections:
        lines = section.strip().split("\n")
        if not lines:
            continue
        header = lines[0].strip().lower()
        body = "\n".join(lines[1:]).strip()
        if header:
            prompts[header] = body

    required = ["architect", "critic", "planner", "writer", "scanner"]
    missing = [k for k in required if k not in prompts]
    if missing:
        raise RuntimeError(f"Prompt sections missing: {', '.join(missing)}")
    return prompts
