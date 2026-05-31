import os
import json
import logging
from typing import Dict

import config
from llm_client import LLMClientError
from workflow_components.resources import get_resource

class ProjectWorkflowMixin:
    def _generate_outline_with_discussion(
        self,
        phase_name: str,
        draft_prompt: str,
        revise_prompt_builder,
        rounds: int,
        output_filename: str,
        prompts: Dict[str, str],
    ) -> str:
        try:
            outline = self.planner_client.generate(
                prompt=draft_prompt,
                system_instruction=prompts["planner"],
            )
        except LLMClientError as e:
            raise RuntimeError(str(e)) from e
        outline = self._enforce_output_language(
            self.planner_client,
            "Planner",
            outline,
            prompts["planner"],
            world_building=True,
        )
        self._log_llm_interaction(
            role="Planner",
            phase=f"{phase_name} Draft",
            prompt=draft_prompt,
            response=outline,
            system_instruction=prompts["planner"],
            world_building=True,
        )

        outline_path = self._save_file(output_filename, outline, self.plot_dir)
        self._append_structured_discussion(
            phase_type="plot",
            role="Planner",
            prompt_text=draft_prompt,
            response_text=outline,
            round_index=0,
            decision=f"{phase_name}_draft_ready",
            needs_revision=None,
            artifact_paths=[outline_path],
        )

        for i in range(max(0, rounds)):
            critique_prompt = get_resource("prompt.world_bible_draft_critique", world_bible=outline)
            critique_prompt += f"\n\n{self._language_rule()}"
            try:
                critique = self.critic_client.generate(
                    prompt=critique_prompt,
                    system_instruction=prompts["critic"],
                )
            except LLMClientError as e:
                raise RuntimeError(str(e)) from e
            critique = self._enforce_output_language(
                self.critic_client,
                "Critic",
                critique,
                prompts["critic"],
                world_building=True,
            )
            self._log_llm_interaction(
                role="Critic",
                phase=f"{phase_name} Critique Round {i + 1}",
                prompt=critique_prompt,
                response=critique,
                system_instruction=prompts["critic"],
                world_building=True,
            )
            self._append_structured_discussion(
                phase_type="plot",
                role="Critic",
                prompt_text=critique_prompt,
                response_text=critique,
                round_index=i + 1,
                decision=f"{phase_name}_critique_generated",
                needs_revision=True,
                artifact_paths=[outline_path],
            )

            revise_prompt = revise_prompt_builder(outline, critique)
            revise_prompt += f"\n\n{self._language_rule()}"
            try:
                outline = self.planner_client.generate(
                    prompt=revise_prompt,
                    system_instruction=prompts["planner"],
                )
            except LLMClientError as e:
                raise RuntimeError(str(e)) from e
            outline = self._enforce_output_language(
                self.planner_client,
                "Planner",
                outline,
                prompts["planner"],
                world_building=True,
            )
            self._log_llm_interaction(
                role="Planner",
                phase=f"{phase_name} Revision Round {i + 1}",
                prompt=revise_prompt,
                response=outline,
                system_instruction=prompts["planner"],
                world_building=True,
            )
            outline_path = self._save_file(output_filename, outline, self.plot_dir)
            self._append_structured_discussion(
                phase_type="plot",
                role="Planner",
                prompt_text=revise_prompt,
                response_text=outline,
                round_index=i + 1,
                decision=f"{phase_name}_revision_applied",
                needs_revision=False,
                artifact_paths=[outline_path],
            )
        return outline

    def start_new_project(self, user_instruction: str) -> str:
        self.logger.info(f"Starting new project ({config.LANGUAGE}) with instruction: {user_instruction}")
        prompts = self._get_system_prompts()

        user_prompt_prefix = get_resource("label.user_request_prefix")
        task_instruction = get_resource("prompt.architect_task")
        architect_prompt = f"{user_prompt_prefix} {user_instruction}\n\n{task_instruction}\n\n{self._language_rule()}"

        try:
            world_bible = self.architect_client.generate(
                prompt=architect_prompt,
                system_instruction=prompts["architect"],
            )
        except LLMClientError as e:
            raise RuntimeError(str(e)) from e
        world_bible = self._enforce_output_language(
            self.architect_client, "Architect", world_bible, prompts["architect"], world_building=True
        )
        self._log_llm_interaction(
            role="Architect",
            phase="World Building Draft",
            prompt=architect_prompt,
            response=world_bible,
            system_instruction=prompts["architect"],
            world_building=True,
        )

        bible_path = self._save_file("world_bible.md", world_bible, self.world_dir)
        self._append_structured_discussion(
            phase_type="world",
            role="Architect",
            prompt_text=architect_prompt,
            response_text=world_bible,
            round_index=0,
            decision="world_bible_draft_ready",
            needs_revision=None,
            artifact_paths=[bible_path],
        )

        rounds = max(0, config.WORLD_DISCUSSION_ROUNDS)
        for i in range(rounds):
            critique_prompt = get_resource("prompt.world_bible_draft_critique", world_bible=world_bible)
            critique_prompt += f"\n\n{self._language_rule()}"
            try:
                critique = self.critic_client.generate(
                    prompt=critique_prompt,
                    system_instruction=prompts["critic"],
                )
            except LLMClientError as e:
                raise RuntimeError(str(e)) from e
            critique = self._enforce_output_language(
                self.critic_client, "Critic", critique, prompts["critic"], world_building=True
            )
            self._log_llm_interaction(
                role="Critic",
                phase=f"World Building Critique Round {i + 1}",
                prompt=critique_prompt,
                response=critique,
                system_instruction=prompts["critic"],
                world_building=True,
            )
            self._append_structured_discussion(
                phase_type="world",
                role="Critic",
                prompt_text=critique_prompt,
                response_text=critique,
                round_index=i + 1,
                decision="world_bible_critique_generated",
                needs_revision=True,
                artifact_paths=[bible_path],
            )
            self._save_file("critique.md", critique, self.critiques_dir)

            revise_prompt = get_resource("prompt.world_bible_revise", world_bible=world_bible, critique=critique)
            revise_prompt += f"\n\n{self._language_rule()}"
            try:
                revised = self.architect_client.generate(
                    prompt=revise_prompt,
                    system_instruction=prompts["architect"],
                )
            except LLMClientError as e:
                raise RuntimeError(str(e)) from e
            revised = self._enforce_output_language(
                self.architect_client, "Architect", revised, prompts["architect"], world_building=True
            )
            self._log_llm_interaction(
                role="Architect",
                phase=f"World Building Revision Round {i + 1}",
                prompt=revise_prompt,
                response=revised,
                system_instruction=prompts["architect"],
                world_building=True,
            )
            world_bible = revised
            bible_path = self._save_file("world_bible.md", world_bible, self.world_dir)
            self._append_structured_discussion(
                phase_type="world",
                role="Architect",
                prompt_text=revise_prompt,
                response_text=revised,
                round_index=i + 1,
                decision="world_bible_revision_applied",
                needs_revision=False,
                artifact_paths=[bible_path],
            )

        plot_draft_prompt = get_resource("prompt.plot_outline_draft", world_bible=world_bible)
        plot_draft_prompt += f"\n\n{self._language_rule()}"
        self._generate_outline_with_discussion(
            phase_name=get_resource("label.plot_outline").strip("："),
            draft_prompt=plot_draft_prompt,
            revise_prompt_builder=(
                lambda current, critique: get_resource("prompt.plot_outline_revise", current=current, critique=critique)
            ),
            rounds=config.PLOT_DISCUSSION_ROUNDS,
            output_filename="plot_outline.md",
            prompts=prompts,
        )
        plot_outline = self._read_text_if_exists(self._plot_outline_path())

        detailed_plot_draft_prompt = get_resource("prompt.detailed_plot_outline_draft", world_bible=world_bible, plot_outline=plot_outline)
        detailed_plot_draft_prompt += f"\n\n{self._language_rule()}"
        self._generate_outline_with_discussion(
            phase_name=get_resource("label.detailed_plot_outline").strip("："),
            draft_prompt=detailed_plot_draft_prompt,
            revise_prompt_builder=(
                lambda current, critique: get_resource("prompt.detailed_plot_outline_revise", current=current, critique=critique)
            ),
            rounds=config.DETAILED_PLOT_DISCUSSION_ROUNDS,
            output_filename="detailed_plot_outline.md",
            prompts=prompts,
        )

        # Seed memory with initial structured facts extracted from the approved world bible.
        scan_prefix = get_resource("label.world_background")
        scan_task = get_resource("prompt.scanner_seed_task")
        scan_task += f" {self._language_rule()}"
        try:
            raw_seed = self.scanner_client.generate(
                prompt=f"{scan_prefix}\n{world_bible}\n\n{scan_task}",
                system_instruction=prompts["scanner"],
            )
            self._log_llm_interaction(
                role="Scanner",
                phase="World Building Seed Extraction",
                prompt=f"{scan_prefix}\n{world_bible}\n\n{scan_task}",
                response=raw_seed,
                system_instruction=prompts["scanner"],
                world_building=True,
            )
            seed_data = self._extract_json(raw_seed)
            if seed_data:
                seed_errors = self._validate_fact_payload(seed_data)
                if seed_errors:
                    self.logger.warning("Initial seed payload validation failed; skip DB seed.")
                    self._save_file(
                        "world_init_facts_invalid.json",
                        json.dumps({"errors": seed_errors, "payload": seed_data}, indent=2, ensure_ascii=False),
                        self.facts_dir,
                    )
                    return bible_path
                self.memory.begin_batch()
                try:
                    self._apply_fact_payload(
                        seed_data,
                        source="init_world",
                        chapter_num=0,
                        source_commit_id="init_world_seed",
                        intent_tag="init_seed",
                    )
                    self.memory.end_batch(success=True)
                except Exception:
                    self.memory.end_batch(success=False)
                    raise
                self._save_file(
                    "world_init_facts.json",
                    json.dumps(seed_data, indent=2, ensure_ascii=False),
                    self.facts_dir,
                )
                self._sync_compact_archives()
        except LLMClientError as e:
            self.logger.warning(f"Initial fact seeding skipped due to scanner error: {e}")

        return bible_path
