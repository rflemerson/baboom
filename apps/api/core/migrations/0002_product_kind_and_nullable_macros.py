"""Add the product kind discriminator and make the nutrition macros nullable."""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Schema migration for the product kind rollout."""

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='nutritionfacts',
            name='nutrition_facts_positive_serving_size',
        ),
        migrations.AddField(
            model_name='product',
            name='kind',
            field=models.CharField(choices=[('SIMPLE', 'Simple Product'), ('COMBO', 'Combo')], default='SIMPLE', help_text='Combos are assembled from other catalog products.', max_length=10, verbose_name='Kind'),
        ),
        migrations.AlterField(
            model_name='nutritionfacts',
            name='carbohydrates',
            field=models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True, verbose_name='Carbs (g)'),
        ),
        migrations.AlterField(
            model_name='nutritionfacts',
            name='energy_kcal',
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Energy (kcal)'),
        ),
        migrations.AlterField(
            model_name='nutritionfacts',
            name='proteins',
            field=models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True, verbose_name='Proteins (g)'),
        ),
        migrations.AlterField(
            model_name='nutritionfacts',
            name='serving_size_grams',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True, verbose_name='Serving Size (g)'),
        ),
        migrations.AlterField(
            model_name='nutritionfacts',
            name='total_fats',
            field=models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True, verbose_name='Total Fats (g)'),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['kind'], name='core_produc_kind_1a67cf_idx'),
        ),
        migrations.AddConstraint(
            model_name='nutritionfacts',
            constraint=models.CheckConstraint(condition=models.Q(('serving_size_grams__gt', 0), ('serving_size_grams__isnull', True), _connector='OR'), name='nutrition_facts_positive_serving_size'),
        ),
        migrations.AddConstraint(
            model_name='productcomponent',
            constraint=models.CheckConstraint(condition=models.Q(('parent', models.F('component')), _negated=True), name='product_component_not_self'),
        ),
    ]
