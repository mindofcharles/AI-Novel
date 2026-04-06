from typing import Optional

import config
from llm_client import LLMClient
from workflow_components.parsing import contains_cjk, language_confidence


from workflow_components.resources import get_res_num, get_resource, is_chinese


class WorkflowLanguageMixin:
    def _language_name(self) -> str:
        return config.LANGUAGE

    def _language_rule(self) -> str:
        return get_resource("prompt.language_rule")

    @staticmethod
    def _contains_cjk(text: str) -> bool:
        return contains_cjk(text)

    def _is_expected_language(self, text: str) -> bool:
        confidence = language_confidence(text)
        if is_chinese():
            if confidence["chinese"] >= get_res_num("lang.confidence_chinese_min"):
                return True
            return self._contains_cjk(text)
        
        # English check
        if confidence["english"] >= get_res_num("lang.confidence_english_min") and \
           confidence["chinese"] <= get_res_num("lang.confidence_chinese_max_for_english"):
            return True
        return not self._contains_cjk(text)

    def _enforce_output_language(
        self,
        client: LLMClient,
        role: str,
        text: str,
        system_instruction: str,
        chapter_num: Optional[int] = None,
        world_building: bool = False,
    ) -> str:
        if self._is_expected_language(text):
            return text
        confidence = language_confidence(text)
        self.logger.warning(
            "Language guard triggered for %s (zh=%.3f, en=%.3f)",
            role,
            confidence["chinese"],
            confidence["english"],
        )
        rewrite_prompt = (
            f"Rewrite the following content in {self._language_name()} only.\n"
            "Keep all details and structure. Output only the rewritten content.\n\n"
            "--- CONTENT BEGIN ---\n"
            f"{text}\n"
            "--- CONTENT END ---"
        )
        rewritten = client.generate(prompt=rewrite_prompt, system_instruction=system_instruction)
        self._log_llm_interaction(
            role=role,
            phase="Language Rewrite",
            prompt=rewrite_prompt,
            response=rewritten,
            system_instruction=system_instruction,
            chapter_num=chapter_num,
            world_building=world_building,
        )
        return rewritten
