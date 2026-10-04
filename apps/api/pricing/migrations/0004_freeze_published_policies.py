"""Freeze published pricing policies in PostgreSQL, below the ORM.

The model refuses these writes too; the trigger also stops raw SQL and bulk
updates. A published policy changes only ``is_default`` and ``updated_at``;
a new behaviour is a new number. Other databases rely on the model guard.
"""

from django.db import migrations

FUNCTION = """
CREATE OR REPLACE FUNCTION pricing_freeze_policy() RETURNS trigger AS $$
BEGIN
    IF OLD.published_at IS NULL THEN
        RETURN COALESCE(NEW, OLD);
    END IF;
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'published policy % cannot be deleted', OLD.id;
    END IF;
    IF (to_jsonb(NEW) - 'is_default' - 'updated_at')
       IS DISTINCT FROM (to_jsonb(OLD) - 'is_default' - 'updated_at') THEN
        RAISE EXCEPTION 'published policy % cannot change', OLD.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


def _run(schema_editor, sql):
    """Execute without parameters, so PL/pgSQL's % is not a placeholder."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(sql)


def _install(apps, schema_editor):
    """Create the function and trigger on PostgreSQL only."""
    _ = apps
    if schema_editor.connection.vendor != "postgresql":
        return
    _run(schema_editor, FUNCTION)
    _run(
        schema_editor,
        "CREATE TRIGGER pricing_freeze_policy BEFORE UPDATE OR DELETE "
        "ON pricing_pricingpolicyrevision FOR EACH ROW "
        "EXECUTE FUNCTION pricing_freeze_policy();",
    )


def _remove(apps, schema_editor):
    """Drop the trigger and function."""
    _ = apps
    if schema_editor.connection.vendor != "postgresql":
        return
    _run(
        schema_editor,
        "DROP TRIGGER IF EXISTS pricing_freeze_policy ON pricing_pricingpolicyrevision;",
    )
    _run(schema_editor, "DROP FUNCTION IF EXISTS pricing_freeze_policy();")


class Migration(migrations.Migration):
    """Install the policy freeze trigger."""

    dependencies = (("pricing", "0003_hourly_projection_refresh"),)

    operations = (migrations.RunPython(_install, _remove),)
