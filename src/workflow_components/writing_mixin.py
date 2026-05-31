import os
import logging
from typing import Dict, Tuple, Optional

import config
from llm_client import LLMClientError
from workflow_components.resources import get_resource

class WritingWorkflowMixin:
    def _critic_review_chapter(self, chapter_num: int, guide_content: str, chapter_text: str, prompts: Dict[str, str]) -> str:
        review_task = get_resource("prompt.critic_review_task")
        output_format = get_resource("prompt.critic_output_format")
        contract_label = get_resource("label.contract")
        chapter_label = get_resource("label.chapter_text")
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

            revise_instruction = get_resource("prompt.writer_revise")
            revise_instruction += f"\n{self._language_rule()}"
            contract_label = get_resource("label.contract")
            chapter_label = get_resource("label.current_chapter")
            critique_label = get_resource("label.critique")
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
                "- " + c[0] + get_resource("ui.status_label", status=c[2])
            )
        if not char_lines:
            char_lines.append(get_resource("ui.no_records_simple"))

        rule_lines = []
        for r in db_rules:
            rule_lines.append(
                get_resource("ui.rule_item_no_newline", category=r[0], content=r[1], strictness=r[2])
            )
        if not rule_lines:
            rule_lines.append(get_resource("ui.rule_no_records_simple"))

        event_lines = []
        for e in db_events:
            event_lines.append(
                get_resource("ui.event_item_no_newline", timestamp=e[3], name=e[1], description=e[2], location=e[6])
            )
        if not event_lines:
            event_lines.append(get_resource("ui.event_no_records_simple"))

        conflict_lines = []
        for conflict in pending_conflicts:
            conflict_lines.append(
                f"- #{conflict[0]} [{conflict[3]}] {conflict[1]}:{conflict[2]} (chapter={conflict[5]})"
            )
        if not conflict_lines:
            conflict_lines.append(get_resource("ui.none_simple"))

        contract_prefix = get_resource("label.contract") + "："
        write_instruction = get_resource("prompt.writer_task", chapter_num=chapter_num)
        write_instruction += f"\n{self._language_rule()}"
        writer_context_label = get_resource("label.writer_context")
        previous_label = get_resource("label.previous_summary")
        chars_label = get_resource("label.character_state")
        rules_label = get_resource("label.world_rules")
        events_label = get_resource("label.recent_events")
        conflicts_label = get_resource("label.pending_conflicts")
        semantic_label = get_resource("label.semantic_details")
        prev_text = previous_summary or get_resource("ui.none_bracket")
        retrieval_policy = (
            get_resource("label.retrieval_policy_detailed", task_type=retrieval_intent.get('task_type'), mode=retrieval_intent.get('mode'), tiers=retrieval_intent.get('required_tiers'))
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

    def review_revise_and_scan(self, chapter_num: int, guide_content: str, chapter_text: str) -> str:
        prompts = self._get_system_prompts()
        revised_text, _ = self._review_and_revise_chapter(chapter_num, guide_content, chapter_text, prompts)
        if revised_text != chapter_text:
            self._save_file(f"chapter_{self._num3(chapter_num)}.md", revised_text, self.chapters_dir)
        return self.scan_chapter(chapter_num)
