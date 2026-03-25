import sqlite3


class MemorySchemaMixin:
    SCHEMA_VERSION = 6

    def _ensure_schema_meta_table(self):
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

    def _table_exists(self, table_name: str) -> bool:
        self.cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
            (table_name,),
        )
        return self.cursor.fetchone() is not None

    def _has_non_meta_tables(self) -> bool:
        self.cursor.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
              AND name != 'schema_meta'
            LIMIT 1
            """
        )
        return self.cursor.fetchone() is not None

    def _get_schema_version(self) -> int:
        self.cursor.execute(
            "SELECT value FROM schema_meta WHERE key = 'schema_version' LIMIT 1"
        )
        row = self.cursor.fetchone()
        if row:
            try:
                return int(row[0])
            except (TypeError, ValueError):
                return 0
        if self._has_non_meta_tables():
            raise RuntimeError(
                "Detected unsupported legacy database without schema version metadata. "
                "Please back up and re-initialize the database."
            )
        return 0

    def _set_schema_version(self, version: int):
        self.cursor.execute(
            """
            INSERT INTO schema_meta (key, value) VALUES ('schema_version', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (str(version),),
        )

    def _migration_001_initial_schema(self):
        self.cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                core_traits TEXT,
                status TEXT DEFAULT 'alive',
                attributes TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )

        self.cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT NOT NULL,
                target_name TEXT NOT NULL,
                relation_type TEXT,
                details TEXT,
                UNIQUE(source_name, target_name)
            )
            '''
        )

        self.cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS world_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                rule_content TEXT NOT NULL,
                strictness INTEGER DEFAULT 1,
                source_commit_id TEXT,
                version INTEGER DEFAULT 1,
                is_deleted INTEGER DEFAULT 0,
                intent_tag TEXT
            )
            '''
        )

        self.cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS timeline (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_name TEXT,
                description TEXT,
                timestamp_str TEXT,
                impact_level INTEGER,
                related_entities TEXT,
                location TEXT,
                source_commit_id TEXT,
                version INTEGER DEFAULT 1,
                is_deleted INTEGER DEFAULT 0,
                intent_tag TEXT
            )
            '''
        )

        self.cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS vector_metadata (
                faiss_id INTEGER PRIMARY KEY,
                content TEXT,
                metadata TEXT,
                source_commit_id TEXT,
                version INTEGER DEFAULT 1,
                is_deleted INTEGER DEFAULT 0,
                intent_tag TEXT,
                timestamp_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )

        self.cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS fact_revisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                entity_key TEXT NOT NULL,
                action TEXT NOT NULL,
                before_json TEXT,
                after_json TEXT,
                source TEXT,
                chapter_num INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )

        self.cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS conflict_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                entity_key TEXT NOT NULL,
                conflict_type TEXT NOT NULL,
                incoming_json TEXT,
                existing_json TEXT,
                source TEXT,
                chapter_num INTEGER,
                blocking_level TEXT DEFAULT 'BLOCKING',
                priority INTEGER DEFAULT 2,
                suggested_action TEXT DEFAULT 'manual_review',
                status TEXT DEFAULT 'PENDING',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP
            )
            '''
        )

        self.cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS chapter_commits (
                commit_id TEXT PRIMARY KEY,
                chapter_num INTEGER,
                source TEXT,
                payload_json TEXT,
                status TEXT DEFAULT 'STARTED',
                conflicts_count INTEGER DEFAULT 0,
                error_message TEXT,
                replay_count INTEGER DEFAULT 0,
                last_replayed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )

    def _migration_002_add_indexes(self):
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_conflict_queue_status_id ON conflict_queue(status, id)"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_conflict_queue_entity ON conflict_queue(entity_type, entity_key)"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_timeline_event_time ON timeline(event_name, timestamp_str)"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_world_rules_category_strictness ON world_rules(category, strictness)"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_fact_revisions_entity ON fact_revisions(entity_type, entity_key, id)"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_chapter_commits_chapter ON chapter_commits(chapter_num, created_at)"
        )

    def _migration_003_conflict_blocking_levels(self):
        self.cursor.execute("PRAGMA table_info(conflict_queue)")
        columns = {row[1] for row in self.cursor.fetchall()}
        if "blocking_level" not in columns:
            self.cursor.execute(
                "ALTER TABLE conflict_queue ADD COLUMN blocking_level TEXT DEFAULT 'BLOCKING'"
            )
        self.cursor.execute(
            "UPDATE conflict_queue SET blocking_level = 'BLOCKING' WHERE blocking_level IS NULL OR blocking_level = ''"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_conflict_queue_blocking ON conflict_queue(status, blocking_level, id)"
        )

    def _migration_004_commit_replay_fields(self):
        self.cursor.execute("PRAGMA table_info(chapter_commits)")
        columns = {row[1] for row in self.cursor.fetchall()}
        if "error_message" not in columns:
            self.cursor.execute("ALTER TABLE chapter_commits ADD COLUMN error_message TEXT")
        if "replay_count" not in columns:
            self.cursor.execute("ALTER TABLE chapter_commits ADD COLUMN replay_count INTEGER DEFAULT 0")
        if "last_replayed_at" not in columns:
            self.cursor.execute("ALTER TABLE chapter_commits ADD COLUMN last_replayed_at TIMESTAMP")
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_chapter_commits_status_created ON chapter_commits(status, created_at)"
        )

    def _migration_005_conflict_triage_fields(self):
        self.cursor.execute("PRAGMA table_info(conflict_queue)")
        columns = {row[1] for row in self.cursor.fetchall()}
        if "priority" not in columns:
            self.cursor.execute("ALTER TABLE conflict_queue ADD COLUMN priority INTEGER DEFAULT 2")
        if "suggested_action" not in columns:
            self.cursor.execute(
                "ALTER TABLE conflict_queue ADD COLUMN suggested_action TEXT DEFAULT 'manual_review'"
            )
        self.cursor.execute("UPDATE conflict_queue SET priority = 2 WHERE priority IS NULL")
        self.cursor.execute(
            "UPDATE conflict_queue SET suggested_action = 'manual_review' WHERE suggested_action IS NULL OR suggested_action = ''"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_conflict_queue_triage ON conflict_queue(status, blocking_level, priority, id)"
        )

    def _migration_006_audit_fields_for_fact_tables(self):
        for table in ("world_rules", "timeline", "vector_metadata"):
            self.cursor.execute(f"PRAGMA table_info({table})")
            columns = {row[1] for row in self.cursor.fetchall()}
            if "source_commit_id" not in columns:
                self.cursor.execute(f"ALTER TABLE {table} ADD COLUMN source_commit_id TEXT")
            if "version" not in columns:
                self.cursor.execute(f"ALTER TABLE {table} ADD COLUMN version INTEGER DEFAULT 1")
            if "is_deleted" not in columns:
                self.cursor.execute(f"ALTER TABLE {table} ADD COLUMN is_deleted INTEGER DEFAULT 0")
            if "intent_tag" not in columns:
                self.cursor.execute(f"ALTER TABLE {table} ADD COLUMN intent_tag TEXT")
            self.cursor.execute(f"UPDATE {table} SET version = 1 WHERE version IS NULL")
            self.cursor.execute(f"UPDATE {table} SET is_deleted = 0 WHERE is_deleted IS NULL")

        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_world_rules_active ON world_rules(is_deleted, category, strictness, id)"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_timeline_active ON timeline(is_deleted, event_name, timestamp_str, id)"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_vector_metadata_active ON vector_metadata(is_deleted, faiss_id)"
        )

    def _run_migrations(self):
        migrations = {
            1: self._migration_001_initial_schema,
            2: self._migration_002_add_indexes,
            3: self._migration_003_conflict_blocking_levels,
            4: self._migration_004_commit_replay_fields,
            5: self._migration_005_conflict_triage_fields,
            6: self._migration_006_audit_fields_for_fact_tables,
        }
        current_version = self._get_schema_version()
        for version in range(current_version + 1, self.SCHEMA_VERSION + 1):
            migration = migrations.get(version)
            if migration is None:
                raise RuntimeError(f"Missing migration for schema version {version}")
            migration()
            self._set_schema_version(version)
            self.conn.commit()

    def get_schema_version(self) -> int:
        return self._get_schema_version()

    def _init_sqlite(self):
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self._ensure_schema_meta_table()
        self._run_migrations()
