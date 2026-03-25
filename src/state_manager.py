import json
from typing import Any, Dict, List, Optional

import config
from memory import MemoryManager


class StoryStateManager:
    """
    DB-facing state manager for write/scan workflows.
    Keeps database logic out of workflow orchestration code.
    """

    def __init__(self, memory: MemoryManager, embedding_client: Any):
        self.memory = memory
        self.embedding_client = embedding_client

    @staticmethod
    def _contains_token(text: str, token: str) -> bool:
        return token.lower() in (text or "").lower()

    @staticmethod
    def _format_semantic_lines(
        intent: Dict[str, object],
        hits: List[Dict],
    ) -> str:
        lines = (
            ["相关三级细节（语义检索）："]
            if config.LANGUAGE == "Chinese"
            else ["Relevant Tier-3 Details (Semantic Retrieval):"]
        )
        lines.append(
            f"- 检索意图: {intent['mode']} | {intent['rationale']}"
            if config.LANGUAGE == "Chinese"
            else f"- Retrieval Intent: {intent['mode']} | {intent['rationale']}"
        )
        focus_entities = intent.get("focus_entities", []) or []
        focus_locations = intent.get("focus_locations", []) or []
        if focus_entities:
            lines.append(
                f"- 关注角色: {', '.join(focus_entities)}"
                if config.LANGUAGE == "Chinese"
                else f"- Focus Entities: {', '.join(focus_entities)}"
            )
        if focus_locations:
            lines.append(
                f"- 关注地点: {', '.join(focus_locations)}"
                if config.LANGUAGE == "Chinese"
                else f"- Focus Locations: {', '.join(focus_locations)}"
            )
        for hit in hits:
            meta = hit.get("metadata") or {}
            location = meta.get("location", "-")
            detail_type = meta.get("type", "-")
            content = hit.get("content", "")
            if config.LANGUAGE == "Chinese":
                lines.append(f"- [{detail_type}] {content}（地点：{location}）")
            else:
                lines.append(f"- [{detail_type}] {content} (Location: {location})")
        return "\n".join(lines) + "\n"

    @staticmethod
    def extract_focus_from_state(db_chars: List[tuple], db_events: List[tuple]) -> Dict[str, List[str]]:
        entities = set()
        locations = set()
        for name, _, status in db_chars:
            if status != "dead":
                entities.add(name)
        for event in db_events:
            related = event[5]
            location = event[6]
            if location and location != "Unknown":
                locations.add(location)
            if related:
                try:
                    for e in json.loads(related):
                        if isinstance(e, str) and e.strip():
                            entities.add(e.strip())
                except Exception:
                    pass
        return {
            "entities": sorted(entities),
            "locations": sorted(locations),
        }

    def build_planner_retrieval_intent(
        self,
        chapter_num: int,
        previous_summary: Optional[str],
        db_chars: List[tuple],
        db_events: List[tuple],
        pending_conflicts: List[tuple],
    ) -> Dict[str, object]:
        return self.classify_query_intent(
            task_type="planner",
            chapter_num=chapter_num,
            previous_summary=previous_summary,
            db_chars=db_chars,
            db_events=db_events,
            pending_conflicts=pending_conflicts,
            user_request="chapter guide generation",
        )

    def classify_query_intent(
        self,
        task_type: str,
        chapter_num: int,
        previous_summary: Optional[str],
        db_chars: List[tuple],
        db_events: List[tuple],
        pending_conflicts: List[tuple],
        user_request: str = "",
    ) -> Dict[str, object]:
        focus = self.extract_focus_from_state(db_chars, db_events)
        has_state = bool(db_chars or db_events or previous_summary)
        has_conflict = bool(pending_conflicts)
        requires_high_recall = task_type in {"writer", "scanner", "review"}
        should_semantic = has_state and (
            chapter_num > 1 or has_conflict or len(db_events) > 0 or bool(previous_summary)
        )
        if requires_high_recall and has_state:
            should_semantic = True
        mode = "continuity_guard" if has_conflict else "continuity_build"
        strict_mode = has_conflict or task_type in {"scanner", "review"}
        rationale = (
            "存在待处理冲突，优先检索冲突相关上下文。"
            if has_conflict and config.LANGUAGE == "Chinese"
            else "Use conflict-aware retrieval to avoid amplifying unresolved contradictions."
            if has_conflict
            else "按角色/事件连续性检索三级细节。"
            if config.LANGUAGE == "Chinese"
            else "Retrieve Tier-3 details for chapter continuity by entity/event context."
        )
        return {
            "task_type": task_type,
            "mode": mode,
            "strict_mode": strict_mode,
            "required_tiers": [1, 2, 3] if should_semantic else [1, 2],
            "should_semantic": should_semantic,
            "focus_entities": focus["entities"][:8],
            "focus_locations": focus["locations"][:5],
            "rationale": rationale,
            "user_request": user_request,
        }

    def get_state_snapshot(self, recent_events_limit: int = 5, conflicts_limit: int = 10) -> Dict[str, List[tuple]]:
        return {
            "characters": self.memory.get_all_characters(),
            "rules": self.memory.get_rules_by_category(),
            "events": self.memory.get_events(limit=recent_events_limit),
            "conflicts": self.memory.get_pending_conflicts(limit=conflicts_limit),
        }

    def sqlite_prefilter_for_intent(
        self,
        intent: Dict[str, object],
        recent_events_limit: int = 5,
        conflicts_limit: int = 10,
    ) -> Dict[str, List[tuple]]:
        snapshot = self.get_state_snapshot(recent_events_limit=recent_events_limit, conflicts_limit=conflicts_limit)
        if intent.get("strict_mode"):
            return snapshot
        focus_entities = intent.get("focus_entities", []) or []
        if not focus_entities:
            return snapshot
        focused_events: List[tuple] = []
        for event in snapshot["events"]:
            related_raw = event[5]
            related_entities: List[str] = []
            if related_raw:
                try:
                    related_entities = json.loads(related_raw)
                except Exception:
                    related_entities = []
            if any(entity in focus_entities for entity in related_entities):
                focused_events.append(event)
        if focused_events:
            snapshot["events"] = focused_events[:recent_events_limit]
        return snapshot

    @staticmethod
    def rerank_semantic_hits(
        hits: List[Dict],
        focus_entities: List[str],
        focus_locations: List[str],
    ) -> List[Dict]:
        ranked = []
        entity_tokens = [x.lower() for x in focus_entities]
        location_tokens = [x.lower() for x in focus_locations]
        for hit in hits:
            meta = hit.get("metadata") or {}
            content = (hit.get("content") or "").lower()
            location = str(meta.get("location", "")).lower()
            base = -float(hit.get("score", 0.0))
            entity_bonus = 0.0
            location_bonus = 0.0
            for token in entity_tokens:
                if token and token in content:
                    entity_bonus += 0.35
            for token in location_tokens:
                if token and (token == location or token in content):
                    location_bonus += 0.5
            rank_score = base + entity_bonus + location_bonus
            ranked.append((rank_score, hit))
        ranked.sort(key=lambda x: x[0], reverse=True)
        return [x[1] for x in ranked]

    def semantic_retrieve_for_intent(
        self,
        intent: Dict[str, object],
        chapter_num: int,
        previous_summary: Optional[str],
        db_events: List[tuple],
    ) -> List[Dict]:
        if not intent.get("should_semantic"):
            return []
        event_fragments = [f"{e[1]} {e[2]}" for e in db_events[:3]]
        focus_entities = intent.get("focus_entities", []) or []
        focus_locations = intent.get("focus_locations", []) or []
        queries = [
            "\n".join(x for x in [f"Chapter {chapter_num}", previous_summary or "", " ".join(event_fragments)] if x),
            f"Entities: {' '.join(focus_entities)}",
            f"Locations: {' '.join(focus_locations)}",
        ]
        merged_hits: List[Dict] = []
        seen = set()
        for q in queries:
            q = q.strip()
            if not q:
                continue
            query_embedding = self.embedding_client.get_embedding(q)
            if not query_embedding:
                continue
            meta_filter = {"location": focus_locations[0]} if focus_locations else None
            hits = self.memory.search_semantic(
                query_embedding,
                k=max(config.TIER_3_SEARCH_LIMIT, 3),
                filter_metadata=meta_filter,
            )
            for hit in hits:
                key = (hit.get("content"), json.dumps(hit.get("metadata", {}), sort_keys=True, ensure_ascii=False))
                if key in seen:
                    continue
                seen.add(key)
                merged_hits.append(hit)
        return merged_hits

    def cross_tier_align_semantic_hits(
        self,
        hits: List[Dict],
        db_chars: List[tuple],
        strict_mode: bool,
    ) -> List[Dict]:
        if not hits:
            return []
        dead_entities = {name for name, _, status in db_chars if status == "dead"}
        if not dead_entities:
            return hits
        aligned: List[Dict] = []
        for hit in hits:
            content = hit.get("content") or ""
            lowered = content.lower()
            blocked = False
            for dead_name in dead_entities:
                if not self._contains_token(lowered, dead_name.lower()):
                    continue
                if self.memory._event_is_historical_or_memorial(content):
                    continue
                if strict_mode or self.memory._event_implies_active_participation(content):
                    blocked = True
                    break
            if not blocked:
                aligned.append(hit)
        return aligned

    def build_context_package(
        self,
        task_type: str,
        chapter_num: int,
        previous_summary: Optional[str],
        recent_events_limit: int = 5,
        conflicts_limit: int = 10,
        user_request: str = "",
    ) -> Dict[str, object]:
        base_snapshot = self.get_state_snapshot(
            recent_events_limit=recent_events_limit,
            conflicts_limit=conflicts_limit,
        )
        intent = self.classify_query_intent(
            task_type=task_type,
            chapter_num=chapter_num,
            previous_summary=previous_summary,
            db_chars=base_snapshot["characters"],
            db_events=base_snapshot["events"],
            pending_conflicts=base_snapshot["conflicts"],
            user_request=user_request,
        )
        snapshot = self.sqlite_prefilter_for_intent(
            intent=intent,
            recent_events_limit=recent_events_limit,
            conflicts_limit=conflicts_limit,
        )
        raw_hits = self.semantic_retrieve_for_intent(
            intent=intent,
            chapter_num=chapter_num,
            previous_summary=previous_summary,
            db_events=snapshot["events"],
        )
        aligned_hits = self.cross_tier_align_semantic_hits(
            hits=raw_hits,
            db_chars=snapshot["characters"],
            strict_mode=bool(intent.get("strict_mode")),
        )
        ranked_hits = self.rerank_semantic_hits(
            aligned_hits,
            intent.get("focus_entities", []) or [],
            intent.get("focus_locations", []) or [],
        )
        top_hits = ranked_hits[: config.TIER_3_SEARCH_LIMIT]
        semantic_summary = (
            "（跳过语义检索：意图判定为无需检索）\n"
            if config.LANGUAGE == "Chinese"
            else "(Semantic retrieval skipped by intent gate)\n"
        )
        if intent.get("should_semantic"):
            semantic_summary = (
                "（无相关三级细节）\n" if config.LANGUAGE == "Chinese" else "(No relevant Tier-3 details)\n"
            )
            if top_hits:
                semantic_summary = self._format_semantic_lines(intent, top_hits)
        return {
            "intent": intent,
            "characters": snapshot["characters"],
            "rules": snapshot["rules"],
            "events": snapshot["events"],
            "conflicts": snapshot["conflicts"],
            "semantic_hits": top_hits,
            "semantic_summary": semantic_summary,
        }

    def semantic_context_for_planner(
        self,
        chapter_num: int,
        previous_summary: Optional[str],
        db_chars: List[tuple],
        db_events: List[tuple],
        pending_conflicts: List[tuple],
    ) -> str:
        intent = self.classify_query_intent(
            task_type="planner",
            chapter_num=chapter_num,
            previous_summary=previous_summary,
            db_chars=db_chars,
            db_events=db_events,
            pending_conflicts=pending_conflicts,
            user_request="planner semantic context",
        )
        raw_hits = self.semantic_retrieve_for_intent(
            intent=intent,
            chapter_num=chapter_num,
            previous_summary=previous_summary,
            db_events=db_events,
        )
        aligned_hits = self.cross_tier_align_semantic_hits(
            hits=raw_hits,
            db_chars=db_chars,
            strict_mode=bool(intent.get("strict_mode")),
        )
        if not intent["should_semantic"]:
            return (
                "（跳过语义检索：意图判定为无需检索）\n"
                if config.LANGUAGE == "Chinese"
                else "(Semantic retrieval skipped by intent gate)\n"
            )
        if not aligned_hits:
            return "（无相关三级细节）\n" if config.LANGUAGE == "Chinese" else "(No relevant Tier-3 details)\n"
        ranked = self.rerank_semantic_hits(
            aligned_hits,
            intent.get("focus_entities", []) or [],
            intent.get("focus_locations", []) or [],
        )
        return self._format_semantic_lines(intent, ranked[: config.TIER_3_SEARCH_LIMIT])

    def apply_fact_payload(
        self,
        data: Dict,
        summary_lines: Optional[List[str]] = None,
        source: str = "unknown",
        chapter_num: Optional[int] = None,
        source_commit_id: Optional[str] = None,
        intent_tag: str = "",
    ) -> int:
        conflicts_before = self.memory.get_pending_conflict_count()
        for char in data.get("new_characters", []):
            self.memory.upsert_character(
                name=char.get("name"),
                core_traits=char.get("core_traits") or {},
                attributes=char.get("attributes") or {},
                status=char.get("status"),
                source=source,
                chapter_num=chapter_num,
            )
            if summary_lines is not None:
                summary_lines.append(
                    f"新角色: {char.get('name')}" if config.LANGUAGE == "Chinese" else f"New Character: {char.get('name')}"
                )

        for char in data.get("updated_characters", []):
            self.memory.upsert_character(
                name=char.get("name"),
                core_traits=char.get("core_traits"),
                attributes=char.get("attributes"),
                status=char.get("status"),
                source=source,
                chapter_num=chapter_num,
            )
            if summary_lines is not None:
                summary_lines.append(
                    f"角色更新: {char.get('name')}"
                    if config.LANGUAGE == "Chinese"
                    else f"Updated Character: {char.get('name')}"
                )

        for rule in data.get("new_rules", []):
            self.memory.add_rule(
                rule.get("category", "General"),
                rule.get("content", ""),
                rule.get("strictness", 1),
                source=source,
                chapter_num=chapter_num,
                source_commit_id=source_commit_id,
                intent_tag=intent_tag,
            )
            if summary_lines is not None:
                summary_lines.append(
                    f"新规则: {rule.get('content')}" if config.LANGUAGE == "Chinese" else f"New Rule: {rule.get('content')}"
                )

        for rel in data.get("relationships", []):
            self.memory.add_relationship(
                rel.get("source"),
                rel.get("target"),
                rel.get("relation_type"),
                rel.get("details"),
                source_tag=source,
                chapter_num=chapter_num,
            )
            if summary_lines is not None:
                summary_lines.append(
                    f"关系: {rel.get('source')} <-> {rel.get('target')}"
                    if config.LANGUAGE == "Chinese"
                    else f"Relationship: {rel.get('source')} <-> {rel.get('target')}"
                )

        for ev in data.get("events", []):
            self.memory.add_event(
                event_name=ev.get("event_name", "Untitled Event"),
                description=ev.get("description", ""),
                timestamp_str=ev.get("timestamp_str", "Unknown Time"),
                impact_level=ev.get("impact_level", 1),
                related_entities=ev.get("related_entities", []),
                location=ev.get("location", "Unknown"),
                source=source,
                chapter_num=chapter_num,
                source_commit_id=source_commit_id,
                intent_tag=intent_tag,
            )
            if summary_lines is not None:
                summary_lines.append(
                    f"事件: {ev.get('event_name')}" if config.LANGUAGE == "Chinese" else f"Event: {ev.get('event_name')}"
                )

        for det in data.get("details", []):
            content = det.get("content")
            if content:
                embedding = self.embedding_client.get_embedding(content)
                if embedding:
                    self.memory.add_semantic_fact(
                        content,
                        embedding,
                        det.get("metadata", {}),
                        source=source,
                        chapter_num=chapter_num,
                        source_commit_id=source_commit_id,
                        intent_tag=intent_tag,
                    )

        conflicts_after = self.memory.get_pending_conflict_count()
        new_conflicts = max(0, conflicts_after - conflicts_before)
        if summary_lines is not None and new_conflicts > 0:
            summary_lines.append(
                f"冲突待处理: {new_conflicts}" if config.LANGUAGE == "Chinese" else f"Conflicts Pending: {new_conflicts}"
            )
        return new_conflicts

    def sync_compact_archives(self) -> Dict[str, str]:
        chars = self.memory.get_all_characters()
        char_lines = ["# 人物档案（精简）", ""] if config.LANGUAGE == "Chinese" else ["# Character Archive (Compact)", ""]
        if not chars:
            char_lines.append("- 暂无人物记录。" if config.LANGUAGE == "Chinese" else "- No characters recorded yet.")
        else:
            for name, _, status in chars:
                char_lines.append(
                    f"- {name}（状态：{status}）" if config.LANGUAGE == "Chinese" else f"- {name} (status: {status})"
                )

        rules = self.memory.get_rules_by_category()
        rule_lines = ["# 世界规则（精简）", ""] if config.LANGUAGE == "Chinese" else ["# World Rules (Compact)", ""]
        if not rules:
            rule_lines.append("- 暂无规则记录。" if config.LANGUAGE == "Chinese" else "- No rules recorded yet.")
        else:
            for category, content, strictness in rules:
                rule_lines.append(
                    f"- [{category}] {content}（严格度：{strictness}）"
                    if config.LANGUAGE == "Chinese"
                    else f"- [{category}] {content} (strictness: {strictness})"
                )
        return {
            "characters_compact.md": "\n".join(char_lines),
            "world_rules_compact.md": "\n".join(rule_lines),
        }

    def auto_resolve_pending_conflicts(self) -> int:
        """
        Strict mode: never auto-apply incoming hard contradiction.
        Keep existing hard facts and resolve all pending conflicts with keep_existing policy.
        """
        rows = self.memory.get_pending_conflicts(limit=500, blocking_only=True)
        resolved = 0
        for row in rows:
            conflict_id = row[0]
            conflict_type = row[3]
            ok = self.memory.resolve_conflict(
                conflict_id,
                action="keep_existing",
                resolver_note=f"auto-strict keep_existing for {conflict_type}",
                source="auto_resolver",
            )
            if ok:
                resolved += 1
        return resolved
