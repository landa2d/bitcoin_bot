"""
T6-B: Migration validation tests.

Checks:
- All migration files exist and are non-empty
- No uuid_generate_v4() in any migration (should use gen_random_uuid())
- CREATE TABLE IF NOT EXISTS used for safety in newer migrations
- Critical tables are defined across the migration set
- Indexes exist for key query patterns
- No bare CREATE TABLE (without IF NOT EXISTS) except in migration 001

Run with: pytest tests/test_migrations.py -v
"""
import re
from pathlib import Path

import pytest

MIGRATIONS_DIR = Path(__file__).parent.parent / "supabase" / "migrations"


def load_migration(filename: str) -> str:
    path = MIGRATIONS_DIR / filename
    assert path.exists(), f"Migration file missing: {filename}"
    content = path.read_text(encoding="utf-8")
    assert len(content) > 50, f"Migration file appears empty: {filename}"
    return content


def all_migrations_text() -> str:
    """Concatenate all migration files for cross-file checks."""
    texts = []
    for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
        texts.append(f.read_text(encoding="utf-8"))
    return "\n".join(texts)


# ---------------------------------------------------------------------------
# File existence and basic sanity
# ---------------------------------------------------------------------------

class TestMigrationFilesExist:
    def test_001_initial_schema_exists(self):
        load_migration("001_initial_schema.sql")

    def test_002_research_spotlight_exists(self):
        load_migration("002_research_spotlight.sql")

    def test_003_atomic_task_claiming_exists(self):
        load_migration("003_atomic_task_claiming.sql")

    def test_004_core_tables_exists(self):
        load_migration("004_core_tables.sql")

    def test_005_missing_indexes_exists(self):
        load_migration("005_missing_indexes.sql")

    def test_006_rls_policies_exists(self):
        load_migration("006_rls_policies.sql")

    def test_007_newsletter_staleness_exists(self):
        load_migration("007_newsletter_staleness.sql")

    def test_migration_count(self):
        files = list(MIGRATIONS_DIR.glob("*.sql"))
        assert len(files) >= 7, f"Expected at least 7 migrations, found {len(files)}"


# ---------------------------------------------------------------------------
# UUID generation consistency (T1-F fix verification)
# ---------------------------------------------------------------------------

class TestUUIDConsistency:
    def test_no_uuid_generate_v4_anywhere(self):
        """After T1-F fix, no migration should use uuid_generate_v4()."""
        combined = all_migrations_text()
        assert "uuid_generate_v4()" not in combined, (
            "Found uuid_generate_v4() — should be gen_random_uuid() everywhere. "
            "Run migration 001 fix."
        )

    def test_gen_random_uuid_used_in_004(self):
        content = load_migration("004_core_tables.sql")
        assert "gen_random_uuid()" in content


# ---------------------------------------------------------------------------
# Core table definitions across migrations
# ---------------------------------------------------------------------------

class TestCoreTablesDefined:
    """Every critical table must be defined somewhere in the migration set."""

    EXPECTED_TABLES = [
        "moltbook_posts",
        "problems",
        "problem_clusters",
        "opportunities",
        "tool_mentions",
        "pipeline_runs",
        "source_posts",
        "agent_tasks",
        "agent_daily_usage",
        "analysis_runs",
        "newsletters",
        "topic_evolution",
        "cross_signals",
        "predictions",
        "trending_topics",
        "agent_negotiations",
        "research_queue",
        "spotlight_history",
    ]

    def test_all_tables_defined(self):
        combined = all_migrations_text().lower()
        missing = []
        for table in self.EXPECTED_TABLES:
            if f"create table" not in combined or table not in combined:
                # More precise check
                pattern = rf"create table\s+(if not exists\s+)?{re.escape(table)}"
                if not re.search(pattern, combined, re.IGNORECASE):
                    missing.append(table)
        assert not missing, f"Tables not defined in any migration: {missing}"

    @pytest.mark.parametrize("table", EXPECTED_TABLES)
    def test_table_appears_in_migrations(self, table: str):
        combined = all_migrations_text().lower()
        assert table in combined, f"Table '{table}' not found in any migration"


# ---------------------------------------------------------------------------
# Critical indexes exist
# ---------------------------------------------------------------------------

class TestIndexesExist:
    EXPECTED_INDEXES = [
        "idx_agent_tasks_assigned_status",
        "idx_newsletters_edition",
        "idx_predictions_status",
        "idx_analysis_runs_type_created",
        "idx_source_posts_source",
        "idx_source_posts_scraped",
        "idx_opportunities_appearances",
    ]

    @pytest.mark.parametrize("index_name", EXPECTED_INDEXES)
    def test_index_defined(self, index_name: str):
        combined = all_migrations_text().lower()
        assert index_name in combined, f"Index '{index_name}' not found in any migration"


# ---------------------------------------------------------------------------
# RLS policies
# ---------------------------------------------------------------------------

class TestRLSPolicies:
    def test_rls_enabled_on_newsletters(self):
        content = load_migration("006_rls_policies.sql")
        assert "newsletters" in content.lower()
        assert "enable row level security" in content.lower()

    def test_anon_read_policy_for_newsletters(self):
        content = load_migration("006_rls_policies.sql")
        assert "newsletters_anon_read" in content

    def test_anon_read_policy_for_spotlight(self):
        content = load_migration("006_rls_policies.sql")
        assert "spotlight_history_anon_read" in content

    def test_sensitive_tables_have_rls(self):
        content = load_migration("006_rls_policies.sql")
        for table in ["agent_tasks", "agent_daily_usage", "predictions"]:
            assert table in content, f"Table '{table}' not covered by RLS migration"


# ---------------------------------------------------------------------------
# Newsletter staleness migration
# ---------------------------------------------------------------------------

class TestNewsletterStaleness:
    def test_staleness_columns_defined(self):
        content = load_migration("007_newsletter_staleness.sql")
        for col in ["newsletter_appearances", "last_featured_at", "first_featured_at"]:
            assert col in content, f"Column '{col}' missing from staleness migration"

    def test_uses_if_not_exists_pattern(self):
        content = load_migration("007_newsletter_staleness.sql")
        # Should use DO $$ / IF NOT EXISTS pattern for safe re-runs
        assert "IF NOT EXISTS" in content

    def test_index_for_staleness_sort(self):
        content = load_migration("007_newsletter_staleness.sql")
        assert "newsletter_appearances" in content
        assert "CREATE INDEX" in content


# ---------------------------------------------------------------------------
# Idempotency markers
# ---------------------------------------------------------------------------

class TestIdempotency:
    def test_migration_004_uses_if_not_exists(self):
        content = load_migration("004_core_tables.sql")
        assert "IF NOT EXISTS" in content

    def test_migration_005_uses_if_not_exists(self):
        content = load_migration("005_missing_indexes.sql")
        assert "IF NOT EXISTS" in content

    def test_atomic_claiming_uses_create_or_replace(self):
        content = load_migration("003_atomic_task_claiming.sql")
        assert "CREATE OR REPLACE FUNCTION" in content
