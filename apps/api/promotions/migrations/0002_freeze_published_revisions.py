"""Freeze published revisions in PostgreSQL, below the ORM.

The models refuse these writes too; the triggers also stop raw SQL, bulk
updates and any client that bypasses the models. Other databases (SQLite in
local development) rely on the model guards.
"""

from django.db import migrations

REVISION_FUNCTION = """
CREATE OR REPLACE FUNCTION promotions_freeze_revision() RETURNS trigger AS $$
BEGIN
    IF OLD.published_at IS NULL THEN
        RETURN COALESCE(NEW, OLD);
    END IF;
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'published revision % cannot be deleted', OLD.id;
    END IF;
    IF (to_jsonb(NEW) - 'status' - 'updated_at')
       IS DISTINCT FROM (to_jsonb(OLD) - 'status' - 'updated_at')
       OR NEW.status = 'draft' THEN
        RAISE EXCEPTION 'published revision % cannot change', OLD.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

# TG_ARGV[0] names the column that points at the owner: a revision id, or an
# effect id whose revision owns the row.
CHILD_FUNCTION = """
CREATE OR REPLACE FUNCTION promotions_freeze_child() RETURNS trigger AS $$
DECLARE
    rows jsonb[];
    item jsonb;
    owner_id bigint;
    published timestamptz;
BEGIN
    IF TG_OP = 'INSERT' THEN
        rows := ARRAY[to_jsonb(NEW)];
    ELSIF TG_OP = 'DELETE' THEN
        rows := ARRAY[to_jsonb(OLD)];
    ELSE
        rows := ARRAY[to_jsonb(OLD), to_jsonb(NEW)];
    END IF;
    FOREACH item IN ARRAY rows LOOP
        owner_id := (item ->> TG_ARGV[0])::bigint;
        IF TG_ARGV[0] = 'effect_id' THEN
            SELECT revision_id INTO owner_id FROM promotions_promotioneffect
            WHERE id = owner_id;
        END IF;
        SELECT published_at INTO published FROM promotions_promotionrevision
        WHERE id = owner_id;
        IF published IS NOT NULL THEN
            RAISE EXCEPTION 'revision % is published; its terms cannot change',
                owner_id;
        END IF;
    END LOOP;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

CHILD_TABLES = (
    ("promotions_activationcode", "revision_id"),
    ("promotions_promotionscope", "revision_id"),
    ("promotions_promotioneffect", "revision_id"),
    ("promotions_rewardterms", "effect_id"),
    ("promotions_compatibilityrule", "revision_id"),
    ("promotions_promotionrevision_evidence", "promotionrevision_id"),
)


def _run(schema_editor, sql):
    """Execute without parameters, so PL/pgSQL's % is not a placeholder."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(sql)


def _install(apps, schema_editor):
    """Create the functions and triggers on PostgreSQL only."""
    _ = apps
    if schema_editor.connection.vendor != "postgresql":
        return
    _run(schema_editor, REVISION_FUNCTION)
    _run(schema_editor, CHILD_FUNCTION)
    _run(
        schema_editor,
        "CREATE TRIGGER promotions_freeze_revision BEFORE UPDATE OR DELETE "
        "ON promotions_promotionrevision FOR EACH ROW "
        "EXECUTE FUNCTION promotions_freeze_revision();",
    )
    for table, owner in CHILD_TABLES:
        _run(
            schema_editor,
            f"CREATE TRIGGER {table}_freeze BEFORE INSERT OR UPDATE OR DELETE "
            f"ON {table} FOR EACH ROW "
            f"EXECUTE FUNCTION promotions_freeze_child('{owner}');",
        )


def _remove(apps, schema_editor):
    """Drop the triggers and functions."""
    _ = apps
    if schema_editor.connection.vendor != "postgresql":
        return
    _run(
        schema_editor,
        "DROP TRIGGER IF EXISTS promotions_freeze_revision "
        "ON promotions_promotionrevision;",
    )
    for table, _owner in CHILD_TABLES:
        _run(schema_editor, f"DROP TRIGGER IF EXISTS {table}_freeze ON {table};")
    _run(schema_editor, "DROP FUNCTION IF EXISTS promotions_freeze_revision();")
    _run(schema_editor, "DROP FUNCTION IF EXISTS promotions_freeze_child();")


class Migration(migrations.Migration):
    """Install the freeze triggers."""

    dependencies = (("promotions", "0001_initial"),)

    operations = (migrations.RunPython(_install, _remove),)
