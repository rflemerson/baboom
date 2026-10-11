"""Name the nutrition-label actives in Portuguese, as the catalog shows them.

``0001_initial`` seeded them in English while curators named every other
active in Portuguese, so the selector mixed both. Only the seeded name is
replaced, so a name a curator already changed stays; slugs never change.
"""

from django.db import migrations

NAMES = {
    "protein": ("Protein", "Proteína"),
    "carbohydrates": ("Carbohydrates", "Carboidratos"),
    "total-sugars": ("Total Sugars", "Açúcares totais"),
    "added-sugars": ("Added Sugars", "Açúcares adicionados"),
    "total-fats": ("Total Fats", "Gorduras totais"),
    "saturated-fats": ("Saturated Fats", "Gorduras saturadas"),
    "trans-fats": ("Trans Fats", "Gorduras trans"),
    "dietary-fiber": ("Dietary Fiber", "Fibra alimentar"),
    "sodium": ("Sodium", "Sódio"),
}


def rename(apps, schema_editor, *, forward: bool = True):
    """Swap each seeded name for the other language's."""
    _ = schema_editor
    active = apps.get_model("core", "Active")
    for slug, (english, portuguese) in NAMES.items():
        old, new = (english, portuguese) if forward else (portuguese, english)
        active.objects.filter(slug=slug, name=old).update(name=new)


def restore(apps, schema_editor):
    """Put the English names back."""
    rename(apps, schema_editor, forward=False)


class Migration(migrations.Migration):
    """Name the label actives in Portuguese."""

    dependencies = (("core", "0011_active_show_in_catalog"),)

    operations = (migrations.RunPython(rename, restore),)
