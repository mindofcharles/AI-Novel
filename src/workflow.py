import os
import logging
import time
import json
from typing import Dict, Optional, Tuple, List

import config
from llm_client import LLMClient, LLMClientError
from memory import MemoryManager
from state_manager import StoryStateManager
from workflow_components.parsing import (
    extract_json_payload,
    needs_revision,
    validate_fact_payload,
)
from workflow_components.prompts import load_system_prompts
from workflow_components.resume_mixin import WorkflowResumeMixin
from workflow_components.io_mixin import WorkflowIOMixin
from workflow_components.language_mixin import WorkflowLanguageMixin


class WorkflowManager(WorkflowResumeMixin, WorkflowIOMixin, WorkflowLanguageMixin):
    def __init__(self):
        self.logger = logging.getLogger("WorkflowManager")
        logging.basicConfig(level=logging.INFO)

        self.architect_client = LLMClient(
            model_type=config.ARCHITECT_MODEL_TYPE,
            model_name=(
                config.ARCHITECT_OPENAI_MODEL_NAME
                if config.ARCHITECT_MODEL_TYPE == "openai"
                else config.ARCHITECT_GEMINI_MODEL_NAME
            ),
            enable_embedding=False,
        )
        self.planner_client = LLMClient(
            model_type=config.PLANNER_MODEL_TYPE,
            model_name=(
                config.PLANNER_OPENAI_MODEL_NAME
                if config.PLANNER_MODEL_TYPE == "openai"
                else config.PLANNER_GEMINI_MODEL_NAME
            ),
            enable_embedding=False,
        )
        self.writer_client = LLMClient(
            model_type=config.WRITER_MODEL_TYPE,
            model_name=(
                config.WRITER_OPENAI_MODEL_NAME
                if config.WRITER_MODEL_TYPE == "openai"
                else config.WRITER_GEMINI_MODEL_NAME
            ),
            enable_embedding=False,
        )
        self.critic_client = LLMClient(
            model_type=config.CRITIC_MODEL_TYPE,
            model_name=(
                config.CRITIC_OPENAI_MODEL_NAME
                if config.CRITIC_MODEL_TYPE == "openai"
                else config.CRITIC_GEMINI_MODEL_NAME
            ),
            enable_embedding=False,
        )
        self.scanner_client = LLMClient(
            model_type=config.SCANNER_MODEL_TYPE,
            model_name=(
                config.SCANNER_OPENAI_MODEL_NAME
                if config.SCANNER_MODEL_TYPE == "openai"
                else config.SCANNER_GEMINI_MODEL_NAME
            ),
            enable_embedding=False,
        )
        # Shared embedding client
        self.embedding_client = LLMClient(model_type=config.PRIMARY_MODEL_TYPE, enable_embedding=True)

        self.memory = MemoryManager(config.DB_PATH, config.FAISS_INDEX_PATH, embedding_dim=config.EMBEDDING_DIM)
        self.state_manager = StoryStateManager(self.memory, self.embedding_client)

        self.world_dir = os.path.join(config.FRAME_DIR, "world")
        self.plot_dir = os.path.join(config.FRAME_DIR, "plot")
        self.guides_dir = os.path.join(config.FRAME_DIR, "chapter_guides")
        self.archives_dir = os.path.join(config.FRAME_DIR, "archives")
        self.chapters_dir = os.path.join(config.OUTPUT_DIR, "chapters")
        self.critiques_dir = os.path.join(config.PROCESS_DIR, "critiques")
        self.discussions_dir = os.path.join(config.PROCESS_DIR, "discussions")
        self.facts_dir = os.path.join(config.PROCESS_DIR, "facts")
        self.reviews_dir = os.path.join(config.PROCESS_DIR, "reviews")
        self.revisions_dir = os.path.join(config.PROCESS_DIR, "revisions")
        self.discussion_log_dir = os.path.join("novel", "Discussion_Log")

        for d in [
            config.OUTPUT_DIR,
            config.FRAME_DIR,
            config.PROCESS_DIR,
            self.world_dir,
            self.plot_dir,
            self.guides_dir,
            self.archives_dir,
            self.chapters_dir,
            self.critiques_dir,
            self.discussions_dir,
            self.facts_dir,
            self.reviews_dir,
            self.revisions_dir,
            self.discussion_log_dir,
        ]:
            os.makedirs(d, exist_ok=True)
        self._ensure_discussion_logs()

    @staticmethod
    def _num3(value: int) -> str:
        return f"{value:03d}"

    def get_guide_path(self, chapter_num: int) -> str:
        return os.path.join(self.guides_dir, f"chapter_{self._num3(chapter_num)}_guide.md")

    def get_chapter_path(self, chapter_num: int) -> str:
        return os.path.join(self.chapters_dir, f"chapter_{self._num3(chapter_num)}.md")

    def get_overview_path(self) -> str:
        return os.path.join("novel", "Novel_Overview.md")

    def _plot_outline_path(self) -> str:
        return os.path.join(self.plot_dir, "plot_outline.md")

    def _detailed_plot_outline_path(self) -> str:
        return os.path.join(self.plot_dir, "detailed_plot_outline.md")

    @staticmethod
    def _default_overview_template() -> str:
        return (
            "# Novel Overview\n\n"
            "Write your high-level novel setup here.\n\n"
            "This file should contain only your requirements for the novel project.\n"
            "The system will read the full document as input.\n\n"
            "Include at least:\n\n"
            "* Genre and tone\n"
            "* Main characters and core relationships\n"
            "* World constraints and major rules\n"
            "* Initial conflict and rough long arc\n"
        )

    def initialize_novel_workspace(self) -> str:
        """
        Initialize only the novel workspace and create Novel_Overview.md.
        This intentionally does not trigger any LLM generation.
        """
        os.makedirs("novel", exist_ok=True)
        for d in [
            config.OUTPUT_DIR,
            config.FRAME_DIR,
            config.PROCESS_DIR,
            self.world_dir,
            self.plot_dir,
            self.guides_dir,
            self.archives_dir,
            self.chapters_dir,
            self.critiques_dir,
            self.discussions_dir,
            self.facts_dir,
            self.reviews_dir,
            self.revisions_dir,
            self.discussion_log_dir,
        ]:
            os.makedirs(d, exist_ok=True)
        self._ensure_discussion_logs()

        overview_path = self.get_overview_path()
        if not os.path.exists(overview_path):
            template = self._default_overview_template()
            with open(overview_path, "w", encoding="utf-8") as f:
                f.write(template)
            self.logger.info(f"Created overview template at {overview_path}")
        return overview_path

    def load_novel_overview(self) -> str:
        overview_path = self.get_overview_path()
        if not os.path.exists(overview_path):
            raise RuntimeError(
                f"Novel overview not found at {overview_path}. Run --init first."
            )

        with open(overview_path, "r", encoding="utf-8") as f:
            overview = f.read().strip()

        if not overview or overview == self._default_overview_template().strip():
            raise RuntimeError(
                f"Novel overview at {overview_path} is empty. Fill it first, then run --start."
            )
        return overview

    def _enforce_conflict_free_state(self, stage: str):
        mode = (getattr(config, "BLOCKING_CONFLICT_MODE", "auto_keep_existing") or "auto_keep_existing").lower()
        if mode == "auto_keep_existing":
            self.state_manager.auto_resolve_pending_conflicts()
        elif mode == "manual_block":
            pass
        else:
            raise RuntimeError(
                f"Invalid BLOCKING_CONFLICT_MODE={mode}. "
                "Expected one of: auto_keep_existing, manual_block."
            )
        blocking_pending = self.memory.get_pending_blocking_conflict_count()
        total_pending = self.memory.get_pending_conflict_count()
        if blocking_pending > 0:
            raise RuntimeError(
                f"Blocked at {stage}: {blocking_pending} unresolved BLOCKING conflicts remain in DB "
                f"(total pending={total_pending}, mode={mode})."
            )

    def _extract_json(self, text: str) -> Optional[Dict]:
        return extract_json_payload(text, logger=self.logger)

    @staticmethod
    def _validate_fact_payload(data: Dict) -> List[str]:
        return validate_fact_payload(data)

    def _apply_fact_payload(
        self,
        data: Dict,
        summary_lines: Optional[List[str]] = None,
        source: str = "unknown",
        chapter_num: Optional[int] = None,
        source_commit_id: Optional[str] = None,
        intent_tag: str = "",
    ) -> int:
        manager = getattr(self, "state_manager", None)
        if manager is None:
            manager = StoryStateManager(getattr(self, "memory", None), getattr(self, "embedding_client", None))
        return manager.apply_fact_payload(
            data=data,
            summary_lines=summary_lines,
            source=source,
            chapter_num=chapter_num,
            source_commit_id=source_commit_id,
            intent_tag=intent_tag,
        )

    @staticmethod
    def _extract_focus_from_state(db_chars: List[tuple], db_events: List[tuple]) -> Dict[str, List[str]]:
        return StoryStateManager.extract_focus_from_state(db_chars, db_events)

    def _build_planner_retrieval_intent(
        self,
        chapter_num: int,
        previous_summary: Optional[str],
        db_chars: List[tuple],
        db_events: List[tuple],
        pending_conflicts: List[tuple],
    ) -> Dict[str, object]:
        manager = getattr(self, "state_manager", None)
        if manager is None:
            manager = StoryStateManager(getattr(self, "memory", None), getattr(self, "embedding_client", None))
        return manager.build_planner_retrieval_intent(
            chapter_num=chapter_num,
            previous_summary=previous_summary,
            db_chars=db_chars,
            db_events=db_events,
            pending_conflicts=pending_conflicts,
        )

    @staticmethod
    def _rerank_semantic_hits(
        hits: List[Dict],
        focus_entities: List[str],
        focus_locations: List[str],
    ) -> List[Dict]:
        return StoryStateManager.rerank_semantic_hits(hits, focus_entities, focus_locations)

    def _semantic_context_for_planner(
        self,
        chapter_num: int,
        previous_summary: Optional[str],
        db_chars: List[tuple],
        db_events: List[tuple],
        pending_conflicts: List[tuple],
    ) -> str:
        manager = getattr(self, "state_manager", None)
        if manager is None:
            manager = StoryStateManager(getattr(self, "memory", None), getattr(self, "embedding_client", None))
        return manager.semantic_context_for_planner(
            chapter_num=chapter_num,
            previous_summary=previous_summary,
            db_chars=db_chars,
            db_events=db_events,
            pending_conflicts=pending_conflicts,
        )

    def _get_system_prompts(self) -> Dict[str, str]:
        return load_system_prompts(config.LANGUAGE, os.path.dirname(__file__))

    def _latest_world_bible_path(self) -> str:
        canonical = os.path.join(self.world_dir, "world_bible.md")
        return canonical

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
            critique_prompt = (
                f"请审查以下内容的逻辑完整性、可执行性与冲突强度，并给出可执行修改建议：\n\n{outline}"
                if config.LANGUAGE == "Chinese"
                else f"Review the following outline for logic, execution clarity, and conflict intensity. Provide concrete revision suggestions:\n\n{outline}"
            )
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

        return outline_path

    def _sync_compact_archives(self):
        manager = getattr(self, "state_manager", None)
        if manager is None:
            manager = StoryStateManager(getattr(self, "memory", None), getattr(self, "embedding_client", None))
        archives = manager.sync_compact_archives()
        for filename, content in archives.items():
            self._save_file(filename, content, self.archives_dir)

    def _critic_review_chapter(self, chapter_num: int, guide_content: str, chapter_text: str, prompts: Dict[str, str]) -> str:
        review_task = (
            "请审查该章节是否与写作契约和既有事实冲突。"
            if config.LANGUAGE == "Chinese"
            else "Review the chapter for contradictions against the writing contract and established facts."
        )
        output_format = (
            "请严格输出:\n是否需要修订: 是/否\n理由: ...\n修订建议: ..."
            if config.LANGUAGE == "Chinese"
            else "Output strictly:\nNEEDS_REVISION: yes/no\nRATIONALE: ...\nPATCH_GUIDANCE: ..."
        )
        contract_label = "写作契约" if config.LANGUAGE == "Chinese" else "Writing Contract"
        chapter_label = "章节正文" if config.LANGUAGE == "Chinese" else "Chapter Text"
        critic_prompt = (
            f"{contract_label}:\n{guide_content}\n\n"
            f"{chapter_label}:\n{chapter_text}\n\n{review_task}\n{output_format}\n{self._language_rule()}"
        )
        review = self.critic_client.generate(
            prompt=critic_prompt,
            system_instruction=prompts["critic"],
        )
        review = self._enforce_output_language(
            self.critic_client, "Critic", review, prompts["critic"], chapter_num=chapter_num
        )
        self._log_llm_interaction(
            role="Critic",
            phase=f"Chapter {self._num3(chapter_num)} Review",
            prompt=critic_prompt,
            response=review,
            system_instruction=prompts["critic"],
            chapter_num=chapter_num,
        )
        self._save_file(f"chapter_{self._num3(chapter_num)}_review.md", review, self.reviews_dir)
        return review

    def _refine_chapter_guide_with_discussion(self, chapter_num: int, guide: str, prompts: Dict[str, str]) -> str:
        rounds = max(0, config.CHAPTER_GUIDE_DISCUSSION_ROUNDS)
        current_guide = guide
        self._append_structured_discussion(
            phase_type="guide",
            role="Planner",
            prompt_text=f"initial_chapter_guide_chapter_{self._num3(chapter_num)}",
            response_text=current_guide,
            chapter_num=chapter_num,
            round_index=0,
            decision="guide_draft_ready",
            needs_revision=None,
            artifact_paths=[self.get_guide_path(chapter_num)],
        )
        for i in range(rounds):
            critique_prompt = (
                "请审查该写作契约的可执行性、人物行为一致性、冲突推进与节奏控制，并给出可执行修订建议。"
                if config.LANGUAGE == "Chinese"
                else "Review this writing contract for executability, character consistency, conflict progression, and pacing. Provide concrete revision guidance."
            )
            critique_prompt += f"\n\n写作契约:\n{current_guide}" if config.LANGUAGE == "Chinese" else f"\n\nWriting Contract:\n{current_guide}"
            critique_prompt += f"\n\n{self._language_rule()}"
            critique = self.critic_client.generate(
                prompt=critique_prompt,
                system_instruction=prompts["critic"],
            )
            critique = self._enforce_output_language(
                self.critic_client, "Critic", critique, prompts["critic"], chapter_num=chapter_num
            )
            self._log_llm_interaction(
                role="Critic",
                phase=f"Chapter {self._num3(chapter_num)} Guide Critique Round {i + 1}",
                prompt=critique_prompt,
                response=critique,
                system_instruction=prompts["critic"],
                chapter_num=chapter_num,
            )
            self._append_structured_discussion(
                phase_type="guide",
                role="Critic",
                prompt_text=critique_prompt,
                response_text=critique,
                chapter_num=chapter_num,
                round_index=i + 1,
                decision="guide_critique_generated",
                needs_revision=True,
                artifact_paths=[self.get_guide_path(chapter_num)],
            )

            revise_prompt = (
                "请根据审稿意见修订该写作契约，保持结构清晰、可执行、并与既有设定一致。\n\n"
                f"当前写作契约:\n{current_guide}\n\n审稿意见:\n{critique}\n\n{self._language_rule()}"
                if config.LANGUAGE == "Chinese"
                else "Revise this writing contract based on the critique. Keep it structured, executable, and consistent with established context.\n\n"
                f"Current Writing Contract:\n{current_guide}\n\nCritique:\n{critique}\n\n{self._language_rule()}"
            )
            current_guide = self.planner_client.generate(
                prompt=revise_prompt,
                system_instruction=prompts["planner"],
            )
            current_guide = self._enforce_output_language(
                self.planner_client, "Planner", current_guide, prompts["planner"], chapter_num=chapter_num
            )
            self._log_llm_interaction(
                role="Planner",
                phase=f"Chapter {self._num3(chapter_num)} Guide Revision Round {i + 1}",
                prompt=revise_prompt,
                response=current_guide,
                system_instruction=prompts["planner"],
                chapter_num=chapter_num,
            )
            self._append_structured_discussion(
                phase_type="guide",
                role="Planner",
                prompt_text=revise_prompt,
                response_text=current_guide,
                chapter_num=chapter_num,
                round_index=i + 1,
                decision="guide_revision_applied",
                needs_revision=False,
                artifact_paths=[self.get_guide_path(chapter_num)],
            )
        return current_guide

    @staticmethod
    def _needs_revision(review_text: str) -> bool:
        return needs_revision(review_text)

    def start_new_project(self, user_instruction: str) -> str:
        self.logger.info(f"Starting new project ({config.LANGUAGE}) with instruction: {user_instruction}")
        prompts = self._get_system_prompts()

        user_prompt_prefix = "用户请求：" if config.LANGUAGE == "Chinese" else "User Request:"
        task_instruction = "设计世界设定集。" if config.LANGUAGE == "Chinese" else "Design the World Bible."
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
            critique_prompt = (
                f"以下是世界设定初稿：\n\n{world_bible}\n\n请给出具体、可执行的改进建议。"
                if config.LANGUAGE == "Chinese"
                else f"Here is the draft World Bible:\n\n{world_bible}\n\nReview and provide concrete improvement suggestions."
            )
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

            revise_prompt = (
                "请基于该审稿意见修订世界设定，保持结构清晰、内容精简并可持续扩展。\n\n"
                f"当前设定：\n{world_bible}\n\n审稿意见：\n{critique}"
                if config.LANGUAGE == "Chinese"
                else "Revise the World Bible based on this critique while keeping it compact and extensible.\n\n"
                f"Current Draft:\n{world_bible}\n\nCritique:\n{critique}"
            )
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

        plot_draft_prompt = (
            "请基于以下世界设定输出《小说情节构思》。\n"
            "要求：强调大阶段剧情推进、核心矛盾演进、关键人物关系变化，不要拆成逐章。\n\n"
            f"世界设定：\n{world_bible}\n\n{self._language_rule()}"
            if config.LANGUAGE == "Chinese"
            else "Based on the following world bible, produce a 'Novel Plot Outline'.\n"
            "Requirements: focus on major arc progression, core conflict evolution, and key relationship shifts; do not split chapter by chapter.\n\n"
            f"World Bible:\n{world_bible}\n\n{self._language_rule()}"
        )
        self._generate_outline_with_discussion(
            phase_name="小说情节构思" if config.LANGUAGE == "Chinese" else "Novel Plot Outline",
            draft_prompt=plot_draft_prompt,
            revise_prompt_builder=(
                lambda current, critique: (
                    "请根据审稿意见修订《小说情节构思》，保持结构清晰且可持续扩展。\n\n"
                    f"当前稿：\n{current}\n\n审稿意见：\n{critique}"
                    if config.LANGUAGE == "Chinese"
                    else "Revise the Novel Plot Outline based on the critique while keeping it structured and extensible.\n\n"
                    f"Current Draft:\n{current}\n\nCritique:\n{critique}"
                )
            ),
            rounds=config.PLOT_DISCUSSION_ROUNDS,
            output_filename="plot_outline.md",
            prompts=prompts,
        )
        plot_outline = self._read_text_if_exists(self._plot_outline_path())

        detailed_plot_draft_prompt = (
            "请基于世界设定与《小说情节构思》输出《小说的具体情节构思》。\n"
            "要求：给出中短期剧情推进、关键场景簇、阶段目标与风险，仍不要写成逐章最终稿。\n\n"
            f"世界设定：\n{world_bible}\n\n"
            f"小说情节构思：\n{plot_outline}\n\n"
            f"{self._language_rule()}"
            if config.LANGUAGE == "Chinese"
            else "Based on the world bible and Novel Plot Outline, produce a 'Detailed Plot Outline'.\n"
            "Requirements: provide near/mid-term plot progression, key scene clusters, stage goals, and risks; still do not turn this into final chapter-by-chapter prose.\n\n"
            f"World Bible:\n{world_bible}\n\n"
            f"Novel Plot Outline:\n{plot_outline}\n\n"
            f"{self._language_rule()}"
        )
        self._generate_outline_with_discussion(
            phase_name="小说具体情节构思" if config.LANGUAGE == "Chinese" else "Detailed Plot Outline",
            draft_prompt=detailed_plot_draft_prompt,
            revise_prompt_builder=(
                lambda current, critique: (
                    "请根据审稿意见修订《小说的具体情节构思》，并保持与世界设定和上一层情节构思一致。\n\n"
                    f"当前稿：\n{current}\n\n审稿意见：\n{critique}"
                    if config.LANGUAGE == "Chinese"
                    else "Revise the Detailed Plot Outline based on critique, and keep it aligned with both the world bible and the high-level plot outline.\n\n"
                    f"Current Draft:\n{current}\n\nCritique:\n{critique}"
                )
            ),
            rounds=config.DETAILED_PLOT_DISCUSSION_ROUNDS,
            output_filename="detailed_plot_outline.md",
            prompts=prompts,
        )

        # Seed memory with initial structured facts extracted from the approved world bible.
        scan_prefix = "世界设定：" if config.LANGUAGE == "Chinese" else "World Bible:"
        scan_task = (
            "请按既定 JSON 结构提取初始事实，用于数据库初始化。仅输出 JSON。"
            if config.LANGUAGE == "Chinese"
            else "Extract initial facts using the scanner JSON schema for DB initialization. Output JSON only."
        )
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

    def generate_chapter_guide(self, chapter_num: int, previous_summary: str = None) -> str:
        self.logger.info(f"Generating guide for Chapter {chapter_num}...")
        self._enforce_conflict_free_state(stage=f"chapter_{self._num3(chapter_num)}_planning")
        prompts = self._get_system_prompts()

        world_bible_path = self._latest_world_bible_path()
        if not os.path.exists(world_bible_path):
            raise RuntimeError("World Bible not found. Run --init first.")

        with open(world_bible_path, "r", encoding="utf-8") as f:
            world_bible = f.read()
        plot_outline = self._read_text_if_exists(self._plot_outline_path())
        detailed_plot_outline = self._read_text_if_exists(self._detailed_plot_outline_path())

        context_pkg = self.state_manager.build_context_package(
            task_type="planner",
            chapter_num=chapter_num,
            previous_summary=previous_summary,
            recent_events_limit=5,
            conflicts_limit=10,
            user_request=f"chapter_{self._num3(chapter_num)}_guide",
        )
        db_chars = context_pkg["characters"]  # type: ignore[assignment]
        char_summary = "当前活跃角色：\n" if config.LANGUAGE == "Chinese" else "Active Characters:\n"
        if db_chars:
            for c in db_chars:
                char_summary += (
                    f"- {c[0]}（状态：{c[2]}）\n"
                    if config.LANGUAGE == "Chinese"
                    else f"- {c[0]} (Status: {c[2]})\n"
                )
        else:
            char_summary += "(暂无记录)\n" if config.LANGUAGE == "Chinese" else "(No records yet)\n"

        db_rules = context_pkg["rules"]  # type: ignore[assignment]
        rule_summary = "动态世界规则：\n" if config.LANGUAGE == "Chinese" else "Dynamic World Rules:\n"
        if db_rules:
            for r in db_rules:
                rule_summary += (
                    f"- [{r[0]}] {r[1]}（严格度：{r[2]}）\n"
                    if config.LANGUAGE == "Chinese"
                    else f"- [{r[0]}] {r[1]} (Strictness: {r[2]})\n"
                )
        else:
            rule_summary += "(暂无规则记录)\n" if config.LANGUAGE == "Chinese" else "(No rules recorded yet)\n"

        db_events = context_pkg["events"]  # type: ignore[assignment]
        event_summary = (
            "近期历史（二级事件）：\n"
            if config.LANGUAGE == "Chinese"
            else "Recent History (Tier 2 Events):\n"
        )
        if db_events:
            for e in db_events:
                event_summary += (
                    f"- [{e[3]}] {e[1]}：{e[2]}（地点：{e[6]}）\n"
                    if config.LANGUAGE == "Chinese"
                    else f"- [{e[3]}] {e[1]}: {e[2]} (Location: {e[6]})\n"
                )
        else:
            event_summary += "(暂无事件记录)\n" if config.LANGUAGE == "Chinese" else "(No events recorded yet)\n"
        pending_conflicts = context_pkg["conflicts"]  # type: ignore[assignment]
        conflict_summary = (
            "待处理冲突：\n"
            if config.LANGUAGE == "Chinese"
            else "Pending Conflicts:\n"
        )
        if pending_conflicts:
            for conflict in pending_conflicts:
                conflict_summary += (
                    f"- #{conflict[0]} [{conflict[3]}] {conflict[1]}:{conflict[2]} (chapter={conflict[5]})\n"
                )
        else:
            conflict_summary += (
                "(暂无)\n" if config.LANGUAGE == "Chinese" else "(none)\n"
            )
        semantic_summary = str(context_pkg["semantic_summary"])
        retrieval_intent = context_pkg["intent"]  # type: ignore[assignment]

        context_prefix = "世界背景：" if config.LANGUAGE == "Chinese" else "World Context:"
        plot_prefix = "小说情节构思：" if config.LANGUAGE == "Chinese" else "Novel Plot Outline:"
        detailed_plot_prefix = (
            "小说的具体情节构思：" if config.LANGUAGE == "Chinese" else "Detailed Plot Outline:"
        )
        prev_summary_prefix = "前情提要：" if config.LANGUAGE == "Chinese" else "Previous Chapter Summary:"
        task_instruction = (
            f"任务：创建第 {chapter_num} 章的写作契约。"
            if config.LANGUAGE == "Chinese"
            else f"Task: Create the Writing Contract for Chapter {chapter_num}."
        )
        task_instruction += f"\n{self._language_rule()}"

        full_prompt = f"{context_prefix}\n{world_bible}\n\n"
        if plot_outline:
            full_prompt += f"{plot_prefix}\n{plot_outline}\n\n"
        if detailed_plot_outline:
            full_prompt += f"{detailed_plot_prefix}\n{detailed_plot_outline}\n\n"
        state_header = "--- 当前状态 ---" if config.LANGUAGE == "Chinese" else "--- CURRENT STATE ---"
        state_footer = "----------------" if config.LANGUAGE == "Chinese" else "---------------------"
        full_prompt += f"{state_header}\n{char_summary}\n{rule_summary}\n{event_summary}\n{state_footer}\n\n"
        full_prompt += conflict_summary + "\n"
        full_prompt += (
            f"检索策略: {retrieval_intent.get('task_type')} | {retrieval_intent.get('mode')} | tiers={retrieval_intent.get('required_tiers')}\n\n"
            if config.LANGUAGE == "Chinese"
            else f"Retrieval Policy: {retrieval_intent.get('task_type')} | {retrieval_intent.get('mode')} | tiers={retrieval_intent.get('required_tiers')}\n\n"
        )
        full_prompt += semantic_summary + "\n"
        if previous_summary:
            full_prompt += f"{prev_summary_prefix} {previous_summary}\n\n"
        full_prompt += task_instruction

        try:
            guide = self.planner_client.generate(prompt=full_prompt, system_instruction=prompts["planner"])
        except LLMClientError as e:
            raise RuntimeError(str(e)) from e
        guide = self._enforce_output_language(
            self.planner_client, "Planner", guide, prompts["planner"], chapter_num=chapter_num
        )
        self._log_llm_interaction(
            role="Planner",
            phase=f"Chapter {self._num3(chapter_num)} Planning",
            prompt=full_prompt,
            response=guide,
            system_instruction=prompts["planner"],
            chapter_num=chapter_num,
        )
        guide = self._refine_chapter_guide_with_discussion(chapter_num, guide, prompts)

        self._save_file(f"chapter_{self._num3(chapter_num)}_guide.md", guide, self.guides_dir)
        return guide

    def write_chapter(self, chapter_num: int, guide_content: str) -> str:
        self.logger.info(f"Writing Chapter {chapter_num}...")
        self._enforce_conflict_free_state(stage=f"chapter_{self._num3(chapter_num)}_writing")
        prompts = self._get_system_prompts()

        previous_summary = self._load_previous_summary(chapter_num - 1) if chapter_num > 1 else None
        context_pkg = self.state_manager.build_context_package(
            task_type="writer",
            chapter_num=chapter_num,
            previous_summary=previous_summary,
            recent_events_limit=8,
            conflicts_limit=10,
            user_request=f"chapter_{self._num3(chapter_num)}_writing",
        )
        db_chars = context_pkg["characters"]  # type: ignore[assignment]
        db_rules = context_pkg["rules"]  # type: ignore[assignment]
        db_events = context_pkg["events"]  # type: ignore[assignment]
        pending_conflicts = context_pkg["conflicts"]  # type: ignore[assignment]
        semantic_context = str(context_pkg["semantic_summary"])
        retrieval_intent = context_pkg["intent"]  # type: ignore[assignment]

        char_lines = []
        for c in db_chars:
            char_lines.append(
                f"- {c[0]}（状态：{c[2]}）"
                if config.LANGUAGE == "Chinese"
                else f"- {c[0]} (Status: {c[2]})"
            )
        if not char_lines:
            char_lines.append("(暂无记录)" if config.LANGUAGE == "Chinese" else "(No records yet)")

        rule_lines = []
        for r in db_rules:
            rule_lines.append(
                f"- [{r[0]}] {r[1]}（严格度：{r[2]}）"
                if config.LANGUAGE == "Chinese"
                else f"- [{r[0]}] {r[1]} (Strictness: {r[2]})"
            )
        if not rule_lines:
            rule_lines.append("(暂无规则记录)" if config.LANGUAGE == "Chinese" else "(No rules recorded yet)")

        event_lines = []
        for e in db_events:
            event_lines.append(
                f"- [{e[3]}] {e[1]}：{e[2]}（地点：{e[6]}）"
                if config.LANGUAGE == "Chinese"
                else f"- [{e[3]}] {e[1]}: {e[2]} (Location: {e[6]})"
            )
        if not event_lines:
            event_lines.append("(暂无事件记录)" if config.LANGUAGE == "Chinese" else "(No events recorded yet)")

        conflict_lines = []
        for conflict in pending_conflicts:
            conflict_lines.append(
                f"- #{conflict[0]} [{conflict[3]}] {conflict[1]}:{conflict[2]} (chapter={conflict[5]})"
            )
        if not conflict_lines:
            conflict_lines.append("(暂无)" if config.LANGUAGE == "Chinese" else "(none)")

        contract_prefix = "写作契约：" if config.LANGUAGE == "Chinese" else "Writing Contract:"
        write_instruction = (
            f"现在撰写第 {chapter_num} 章。"
            if config.LANGUAGE == "Chinese"
            else f"Write Chapter {chapter_num} now."
        )
        write_instruction += f"\n{self._language_rule()}"
        writer_context_label = "写作上下文" if config.LANGUAGE == "Chinese" else "Writer Context"
        previous_label = "前章摘要" if config.LANGUAGE == "Chinese" else "Previous Chapter Summary"
        chars_label = "角色状态" if config.LANGUAGE == "Chinese" else "Character State"
        rules_label = "世界规则" if config.LANGUAGE == "Chinese" else "World Rules"
        events_label = "近期事件" if config.LANGUAGE == "Chinese" else "Recent Events"
        conflicts_label = "待处理冲突" if config.LANGUAGE == "Chinese" else "Pending Conflicts"
        semantic_label = "三级语义细节" if config.LANGUAGE == "Chinese" else "Tier-3 Semantic Details"
        prev_text = previous_summary or ("（无）" if config.LANGUAGE == "Chinese" else "(none)")
        retrieval_policy = (
            f"检索策略:\n- task={retrieval_intent.get('task_type')} mode={retrieval_intent.get('mode')} tiers={retrieval_intent.get('required_tiers')}\n\n"
            if config.LANGUAGE == "Chinese"
            else f"Retrieval Policy:\n- task={retrieval_intent.get('task_type')} mode={retrieval_intent.get('mode')} tiers={retrieval_intent.get('required_tiers')}\n\n"
        )
        writer_prompt = (
            f"{contract_prefix}\n{guide_content}\n\n"
            f"{writer_context_label}:\n"
            f"{previous_label}:\n{prev_text}\n\n"
            f"{retrieval_policy}"
            f"{chars_label}:\n{'\n'.join(char_lines)}\n\n"
            f"{rules_label}:\n{'\n'.join(rule_lines)}\n\n"
            f"{events_label}:\n{'\n'.join(event_lines)}\n\n"
            f"{conflicts_label}:\n{'\n'.join(conflict_lines)}\n\n"
            f"{semantic_label}:\n{semantic_context}\n"
            f"{write_instruction}"
        )

        try:
            chapter_text = self.writer_client.generate(
                prompt=writer_prompt,
                system_instruction=prompts["writer"],
            )
        except LLMClientError as e:
            raise RuntimeError(str(e)) from e
        chapter_text = self._enforce_output_language(
            self.writer_client, "Writer", chapter_text, prompts["writer"], chapter_num=chapter_num
        )
        self._log_llm_interaction(
            role="Writer",
            phase=f"Chapter {self._num3(chapter_num)} Draft",
            prompt=writer_prompt,
            response=chapter_text,
            system_instruction=prompts["writer"],
            chapter_num=chapter_num,
        )
        self._save_file(f"chapter_{self._num3(chapter_num)}.md", chapter_text, self.chapters_dir)
        return chapter_text

    def _review_and_revise_chapter(self, chapter_num: int, guide: str, chapter_text: str, prompts: Dict[str, str]) -> Tuple[str, str]:
        current_text = chapter_text
        latest_review = ""
        rounds = max(0, config.CHAPTER_TEXT_DISCUSSION_ROUNDS)
        self._append_structured_discussion(
            phase_type="chapter_text",
            role="Writer",
            prompt_text=f"chapter_{self._num3(chapter_num)}_draft_ready",
            response_text=current_text,
            chapter_num=chapter_num,
            round_index=0,
            decision="chapter_draft_ready",
            needs_revision=None,
            artifact_paths=[self.get_chapter_path(chapter_num)],
        )
        for round_idx in range(rounds):
            review = self._critic_review_chapter(chapter_num, guide, current_text, prompts)
            latest_review = review
            if not self._needs_revision(review):
                self._append_structured_discussion(
                    phase_type="chapter_text",
                    role="Critic",
                    prompt_text=f"chapter_{self._num3(chapter_num)}_review",
                    response_text=review,
                    chapter_num=chapter_num,
                    round_index=round_idx + 1,
                    decision="review_pass_no_revision",
                    needs_revision=False,
                    artifact_paths=[self.get_chapter_path(chapter_num)],
                )
                break
            self._append_structured_discussion(
                phase_type="chapter_text",
                role="Critic",
                prompt_text=f"chapter_{self._num3(chapter_num)}_review",
                response_text=review,
                chapter_num=chapter_num,
                round_index=round_idx + 1,
                decision="review_requests_revision",
                needs_revision=True,
                artifact_paths=[self.get_chapter_path(chapter_num)],
            )

            revise_instruction = (
                "根据审稿意见修订章节，仅输出修订后的正文。"
                if config.LANGUAGE == "Chinese"
                else "Revise the chapter based on critique. Output only the revised chapter text."
            )
            revise_instruction += f"\n{self._language_rule()}"
            contract_label = "写作契约" if config.LANGUAGE == "Chinese" else "Writing Contract"
            chapter_label = "当前章节正文" if config.LANGUAGE == "Chinese" else "Current Chapter"
            critique_label = "审稿意见" if config.LANGUAGE == "Chinese" else "Critique"
            revise_prompt = (
                f"{contract_label}:\n{guide}\n\n"
                f"{chapter_label}:\n{current_text}\n\n"
                f"{critique_label}:\n{review}\n\n{revise_instruction}"
            )
            try:
                revised = self.writer_client.generate(
                    prompt=revise_prompt,
                    system_instruction=prompts["writer"],
                )
            except LLMClientError as e:
                raise RuntimeError(str(e)) from e
            revised = self._enforce_output_language(
                self.writer_client, "Writer", revised, prompts["writer"], chapter_num=chapter_num
            )
            self._log_llm_interaction(
                role="Writer",
                phase=f"Chapter {self._num3(chapter_num)} Revision Round {round_idx + 1}",
                prompt=revise_prompt,
                response=revised,
                system_instruction=prompts["writer"],
                chapter_num=chapter_num,
            )
            current_text = revised
            self._save_file(
                f"chapter_{self._num3(chapter_num)}_revision_round_{self._num3(round_idx + 1)}.md",
                revised,
                self.revisions_dir,
            )
            self._save_file(f"chapter_{self._num3(chapter_num)}.md", current_text, self.chapters_dir)
            self._append_structured_discussion(
                phase_type="chapter_text",
                role="Writer",
                prompt_text=revise_prompt,
                response_text=current_text,
                chapter_num=chapter_num,
                round_index=round_idx + 1,
                decision="chapter_revision_applied",
                needs_revision=True,
                artifact_paths=[
                    self.get_chapter_path(chapter_num),
                    os.path.join(
                        self.revisions_dir,
                        f"chapter_{self._num3(chapter_num)}_revision_round_{self._num3(round_idx + 1)}.md",
                    ),
                ],
            )
        return current_text, latest_review

    def scan_chapter(self, chapter_num: int) -> str:
        self.logger.info(f"Scanning Chapter {chapter_num} for facts...")
        prompts = self._get_system_prompts()

        path = self.get_chapter_path(chapter_num)
        try:
            with open(path, "r", encoding="utf-8") as f:
                chapter_text = f.read()
        except FileNotFoundError:
            raise RuntimeError(f"Chapter {chapter_num} not found.")

        text_prefix = "章节正文：" if config.LANGUAGE == "Chinese" else "Chapter Text:"
        extract_instruction = "现在提取事实 (JSON)。" if config.LANGUAGE == "Chinese" else "Extract facts (JSON) now."
        scanner_prompt = f"{text_prefix}\n{chapter_text}\n\n{extract_instruction}\n{self._language_rule()}"

        try:
            raw_response = self.scanner_client.generate(
                prompt=scanner_prompt,
                system_instruction=prompts["scanner"],
            )
        except LLMClientError as e:
            raise RuntimeError(str(e)) from e
        self._log_llm_interaction(
            role="Scanner",
            phase=f"Chapter {self._num3(chapter_num)} Extraction",
            prompt=scanner_prompt,
            response=raw_response,
            system_instruction=prompts["scanner"],
            chapter_num=chapter_num,
        )

        data = self._extract_json(raw_response)
        summary_lines = (
            [f"第 {chapter_num} 章摘要："]
            if config.LANGUAGE == "Chinese"
            else [f"Summary for Chapter {chapter_num}:"]
        )

        if not data:
            self._save_file(
                f"chapter_{self._num3(chapter_num)}_facts_raw.txt",
                raw_response,
                self.facts_dir,
            )
            raise RuntimeError("Scanner returned invalid JSON.")
        validation_errors = self._validate_fact_payload(data)
        if validation_errors:
            self._save_file(
                f"chapter_{self._num3(chapter_num)}_facts_invalid.json",
                json.dumps({"errors": validation_errors, "payload": data}, indent=2, ensure_ascii=False),
                self.facts_dir,
            )
            raise RuntimeError("Scanner payload failed schema validation.")
        commit_id = self.memory.begin_chapter_commit(chapter_num, source="scan_chapter", payload=data)
        try:
            self.memory.begin_batch()
            new_conflicts = self._apply_fact_payload(
                data,
                summary_lines=summary_lines,
                source="scan_chapter",
                chapter_num=chapter_num,
                source_commit_id=commit_id,
                intent_tag="scan_extract",
            )
            self.memory.end_batch(success=True)
            self.memory.finalize_chapter_commit(commit_id, status="COMPLETED", conflicts_count=new_conflicts)
        except Exception as e:
            self.memory.end_batch(success=False)
            self.memory.finalize_chapter_commit(
                commit_id,
                status="FAILED",
                conflicts_count=0,
                error_message=str(e),
            )
            raise
        summary_lines.append(
            f"提交ID: {commit_id}"
            if config.LANGUAGE == "Chinese"
            else f"Commit ID: {commit_id}"
        )

        self._save_file(
            f"chapter_{self._num3(chapter_num)}_facts.json",
            json.dumps(data, indent=2, ensure_ascii=False),
            self.facts_dir,
        )

        summary_text = "\n".join(summary_lines)
        self._save_file(
            f"chapter_{self._num3(chapter_num)}_facts_summary.md",
            summary_text,
            self.facts_dir,
        )
        self._sync_compact_archives()
        self._enforce_conflict_free_state(stage=f"chapter_{self._num3(chapter_num)}_post_scan")
        return summary_text

    def review_revise_and_scan(self, chapter_num: int, guide_content: str, chapter_text: str) -> str:
        prompts = self._get_system_prompts()
        revised_text, _ = self._review_and_revise_chapter(chapter_num, guide_content, chapter_text, prompts)
        if revised_text != chapter_text:
            self._save_file(f"chapter_{self._num3(chapter_num)}.md", revised_text, self.chapters_dir)
        return self.scan_chapter(chapter_num)

    def list_pending_conflicts(self, limit: int = 50, level: Optional[str] = None) -> List[tuple]:
        return self.memory.get_pending_conflicts(limit=limit, blocking_level=level)

    def list_pending_conflicts_detailed(self, limit: int = 50, level: Optional[str] = None) -> List[Dict]:
        return self.memory.get_pending_conflict_diagnostics(limit=limit, blocking_level=level)

    def list_pending_conflict_triage(self, limit: int = 50, level: Optional[str] = None) -> List[Dict]:
        return self.memory.get_pending_conflict_triage(limit=limit, blocking_level=level)

    def resolve_pending_conflict(self, conflict_id: int, action: str, note: str = "") -> bool:
        return self.memory.resolve_conflict(conflict_id=conflict_id, action=action, resolver_note=note)

    def batch_triage_non_blocking(self, limit: int = 50, note: str = "batch triage keep_existing") -> int:
        rows = self.memory.get_pending_conflicts(limit=limit, blocking_level=self.memory.NON_BLOCKING)
        resolved = 0
        for row in rows:
            conflict_id = row[0]
            ok = self.memory.resolve_conflict(
                conflict_id=conflict_id,
                action="keep_existing",
                resolver_note=note,
                source="batch_triage",
            )
            if ok:
                resolved += 1
        return resolved

    def list_failed_chapter_commits(self, limit: int = 20) -> List[tuple]:
        return self.memory.get_failed_chapter_commits(limit=limit)

    def replay_chapter_commit(self, commit_id: str) -> bool:
        row = self.memory.get_chapter_commit(commit_id)
        if not row:
            return False
        status = row[4]
        payload_json = row[3]
        chapter_num = row[1]
        if status == "COMPLETED":
            return True
        if not payload_json:
            self.memory.finalize_chapter_commit(
                commit_id,
                status="FAILED",
                conflicts_count=0,
                error_message="Replay skipped: empty payload_json.",
            )
            return False
        try:
            payload = json.loads(payload_json)
        except json.JSONDecodeError:
            self.memory.finalize_chapter_commit(
                commit_id,
                status="FAILED",
                conflicts_count=0,
                error_message="Replay failed: payload_json decode error.",
            )
            return False
        try:
            self.memory.begin_batch()
            conflicts = self._apply_fact_payload(
                payload,
                summary_lines=None,
                source="replay_commit",
                chapter_num=chapter_num,
                source_commit_id=commit_id,
                intent_tag="replay_commit",
            )
            self.memory.end_batch(success=True)
            self.memory.finalize_chapter_commit(
                commit_id,
                status="COMPLETED",
                conflicts_count=conflicts,
                error_message="",
            )
            self._sync_compact_archives()
            return True
        except Exception as e:
            self.memory.end_batch(success=False)
            self.memory.finalize_chapter_commit(
                commit_id,
                status="FAILED",
                conflicts_count=0,
                error_message=f"Replay failed: {e}",
            )
            return False

    def rebuild_vector_index(self) -> Dict[str, int]:
        return self.memory.rebuild_vector_index_from_metadata(self.embedding_client.get_embedding)
