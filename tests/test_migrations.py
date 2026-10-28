"""Migration files: checks that need no database."""

import re

from db import writer

# Must match the CHECK on tender.schema_migrations.version.
VERSION = re.compile(r"^[0-9]{4}_[a-z0-9_]+$")


def test_every_migration_has_a_valid_unique_version() -> None:
    versions = [version for version, _ in writer._migrations()]

    assert versions, "no migrations found"
    assert all(VERSION.match(v) for v in versions), versions
    numbers = [v[:4] for v in versions]
    assert len(numbers) == len(set(numbers)), "two migrations share a number"


def test_migrations_are_also_in_schema_sql() -> None:
    # schema.sql must stay the full current schema: a fresh database records
    # every migration as applied without running it.
    schema = writer.SCHEMA_SQL.read_text(encoding="utf-8")

    assert "birth_date  date CHECK (birth_date >= DATE '1900-01-01')" in schema
    assert "CREATE TABLE schema_migrations" in schema
    assert "annual_returns_checked boolean NOT NULL DEFAULT false" in schema
