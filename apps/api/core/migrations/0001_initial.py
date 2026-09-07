"""Initial migration for the catalog, nutrition and pricing models."""

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models
from django.utils.text import slugify

LABEL_ACTIVES = (
    ("Protein", "g", "proteins"),
    ("Carbohydrates", "g", "carbohydrates"),
    ("Total Sugars", "g", "total_sugars"),
    ("Added Sugars", "g", "added_sugars"),
    ("Total Fats", "g", "total_fats"),
    ("Saturated Fats", "g", "saturated_fats"),
    ("Trans Fats", "g", "trans_fats"),
    ("Dietary Fiber", "g", "dietary_fiber"),
    ("Sodium", "mg", "sodium"),
)


def seed_label_actives(apps, schema_editor):
    """Seed the actives the nutrition label carries in its own columns."""
    active_model = apps.get_model("core", "Active")
    for name, unit, field in LABEL_ACTIVES:
        active_model.objects.get_or_create(
            slug=slugify(name),
            defaults={"name": name, "display_unit": unit, "nutrition_field": field},
        )


def drop_label_actives(apps, schema_editor):
    """Remove the seeded actives."""
    apps.get_model("core", "Active").objects.filter(
        slug__in=[slugify(name) for name, _unit, _field in LABEL_ACTIVES],
    ).delete()


class Migration(migrations.Migration):
    """Initial catalog schema, with the actives the label columns map onto."""

    initial = True

    dependencies = [
        ('offers', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Active',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, editable=False, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='Name')),
                ('slug', models.SlugField(max_length=100, unique=True, verbose_name='Slug')),
                ('display_unit', models.CharField(choices=[('-', '-'), ('g', 'g'), ('mg', 'mg'), ('mcg', 'mcg'), ('kg', 'kg'), ('kcal', 'kcal'), ('IU', 'IU'), ('%', '%')], default='g', help_text='Unit this active is presented in; storage stays canonical.', max_length=10, verbose_name='Display Unit')),
                ('nutrition_field', models.CharField(blank=True, choices=[('proteins', 'proteins'), ('carbohydrates', 'carbohydrates'), ('total_sugars', 'total_sugars'), ('added_sugars', 'added_sugars'), ('total_fats', 'total_fats'), ('saturated_fats', 'saturated_fats'), ('trans_fats', 'trans_fats'), ('dietary_fiber', 'dietary_fiber'), ('sodium', 'sodium')], default='', help_text='Scalar nutrition column carrying this active. Leave empty to read it from the nutrition active rows.', max_length=30, verbose_name='Nutrition Label Field')),
                ('description', models.TextField(blank=True, help_text='Active description', verbose_name='Description')),
            ],
            options={
                'verbose_name': 'Active',
                'verbose_name_plural': 'Actives',
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='AlertSubscriber',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, editable=False, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('email', models.EmailField(max_length=254, unique=True, verbose_name='Email')),
                ('is_active', models.BooleanField(default=True, verbose_name='Active')),
            ],
            options={
                'verbose_name': 'Alert Subscriber',
                'verbose_name_plural': 'Alert Subscribers',
            },
        ),
        migrations.CreateModel(
            name='APIKey',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, editable=False, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('name', models.CharField(help_text='Who is this key for?', max_length=100, verbose_name='Client Name')),
                ('key', models.CharField(db_index=True, editable=False, max_length=64, unique=True, verbose_name='API Key')),
                ('is_active', models.BooleanField(default=True, verbose_name='Active')),
            ],
            options={
                'verbose_name': 'API Key',
                'verbose_name_plural': 'API Keys',
            },
        ),
        migrations.CreateModel(
            name='Brand',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, editable=False, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='Name')),
                ('display_name', models.CharField(max_length=100, unique=True, verbose_name='Display Name')),
                ('description', models.TextField(blank=True, help_text='Brand description', verbose_name='Description')),
            ],
            options={
                'verbose_name': 'Brand',
                'verbose_name_plural': 'Brands',
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='Flavor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, editable=False, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='Name')),
                ('description', models.TextField(blank=True, help_text='Flavor description', verbose_name='Description')),
            ],
            options={
                'verbose_name': 'Flavor',
                'verbose_name_plural': 'Flavors',
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='Store',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, editable=False, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='Name')),
                ('display_name', models.CharField(max_length=100, unique=True, verbose_name='Display Name')),
                ('description', models.TextField(blank=True, help_text='Store description', verbose_name='Description')),
            ],
            options={
                'verbose_name': 'Store',
                'verbose_name_plural': 'Stores',
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, editable=False, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('path', models.CharField(max_length=255, unique=True)),
                ('depth', models.PositiveIntegerField()),
                ('numchild', models.PositiveIntegerField(default=0)),
                ('name', models.CharField(help_text='Unique tag name', max_length=100, unique=True, verbose_name='Name')),
                ('description', models.TextField(blank=True, help_text='Tag description', verbose_name='Description')),
            ],
            options={
                'verbose_name': 'Tag',
                'verbose_name_plural': 'Tags',
            },
        ),
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, editable=False, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('path', models.CharField(max_length=255, unique=True)),
                ('depth', models.PositiveIntegerField()),
                ('numchild', models.PositiveIntegerField(default=0)),
                ('name', models.CharField(help_text='Unique category name', max_length=100, unique=True, verbose_name='Name')),
                ('description', models.TextField(blank=True, help_text='Category description', verbose_name='Description')),
                ('default_active', models.ForeignKey(blank=True, help_text='Active this category is ranked by when none is requested.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='default_for_categories', to='core.active', verbose_name='Default Active')),
            ],
            options={
                'verbose_name': 'Category',
                'verbose_name_plural': 'Categories',
            },
        ),
        migrations.CreateModel(
            name='NutritionFacts',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, editable=False, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('description', models.CharField(blank=True, help_text="E.g. 'Saborizada' or 'Natural' to identify this table in the admin.", max_length=200, verbose_name='Internal Label')),
                ('serving_size', models.DecimalField(blank=True, decimal_places=3, max_digits=16, null=True, verbose_name='Serving Size')),
                ('energy', models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True, verbose_name='Energy')),
                ('proteins', models.DecimalField(blank=True, decimal_places=3, max_digits=16, null=True, verbose_name='Proteins')),
                ('carbohydrates', models.DecimalField(blank=True, decimal_places=3, max_digits=16, null=True, verbose_name='Carbs')),
                ('total_sugars', models.DecimalField(blank=True, decimal_places=3, default=0, max_digits=16, null=True, verbose_name='Total Sugars')),
                ('added_sugars', models.DecimalField(blank=True, decimal_places=3, default=0, max_digits=16, null=True, verbose_name='Added Sugars')),
                ('total_fats', models.DecimalField(blank=True, decimal_places=3, max_digits=16, null=True, verbose_name='Total Fats')),
                ('saturated_fats', models.DecimalField(blank=True, decimal_places=3, default=0, max_digits=16, null=True, verbose_name='Saturated Fats')),
                ('trans_fats', models.DecimalField(blank=True, decimal_places=3, default=0, max_digits=16, null=True, verbose_name='Trans Fats')),
                ('dietary_fiber', models.DecimalField(blank=True, decimal_places=3, default=0, max_digits=16, null=True, verbose_name='Dietary Fiber')),
                ('sodium', models.DecimalField(blank=True, decimal_places=3, default=0, max_digits=16, null=True, verbose_name='Sodium')),
                ('content_hash', models.CharField(blank=True, db_index=True, editable=False, help_text='SHA-256 fingerprint of the nutritional values.', max_length=64, verbose_name='Content Hash')),
            ],
            options={
                'verbose_name': 'Nutrition Facts',
                'verbose_name_plural': 'Nutrition Facts',
                'constraints': [models.CheckConstraint(condition=models.Q(('serving_size__gt', 0), ('serving_size__isnull', True), _connector='OR'), name='nutrition_facts_positive_serving_size')],
            },
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, editable=False, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('name', models.CharField(max_length=200, verbose_name='Product Name')),
                ('kind', models.CharField(choices=[('SIMPLE', 'Simple Product'), ('COMBO', 'Combo')], default='SIMPLE', help_text='Combos are assembled from other catalog products.', max_length=10, verbose_name='Kind')),
                ('description', models.TextField(blank=True, help_text='Marketing description', verbose_name='Description')),
                ('net_mass', models.DecimalField(blank=True, decimal_places=3, help_text='Net content of the package, stored in the canonical unit.', max_digits=16, null=True, verbose_name='Net Mass')),
                ('ean', models.CharField(blank=True, help_text='European Article Number / Global Trade Item Number', max_length=14, null=True, unique=True, verbose_name='EAN/GTIN')),
                ('packaging', models.CharField(choices=[('REFILL', 'Refill Package'), ('CONTAINER', 'Container Package'), ('BAR', 'Bar'), ('OTHER', 'Other')], default='CONTAINER', max_length=20, verbose_name='Packaging Type')),
                ('is_published', models.BooleanField(default=False, help_text='If checked, this product will be visible on the public website.', verbose_name='Published')),
                ('brand', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.brand', verbose_name='Brand')),
                ('category', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.category', verbose_name='Product Category')),
            ],
            options={
                'verbose_name': 'Product',
                'verbose_name_plural': 'Products',
                'ordering': ('brand__name', 'name'),
            },
        ),
        migrations.CreateModel(
            name='ProductStore',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, editable=False, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('affiliate_link', models.URLField(blank=True, default='', help_text='URL with affiliate tracking parameters', max_length=500, verbose_name='Affiliate Tracking URL')),
                ('offer', models.OneToOneField(blank=True, help_text='Merchant offer that holds the price series for this listing', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='product_store', to='offers.offer', verbose_name='Merchant Offer')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='store_links', to='core.product', verbose_name='Related Product')),
                ('store', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.store', verbose_name='Associated Store')),
            ],
            options={
                'verbose_name': 'Store Product Link',
                'verbose_name_plural': 'Store Product Links',
                'ordering': ('store__name', 'product__name'),
            },
        ),
        migrations.AddField(
            model_name='product',
            name='stores',
            field=models.ManyToManyField(blank=True, through='core.ProductStore', to='core.store', verbose_name='Available In Stores'),
        ),
        migrations.AddField(
            model_name='product',
            name='tags',
            field=models.ManyToManyField(blank=True, to='core.tag', verbose_name='Product Tags'),
        ),
        migrations.CreateModel(
            name='NutritionActive',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, editable=False, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('amount', models.DecimalField(decimal_places=3, help_text='Stored in the canonical unit of the declared dimension.', max_digits=16, verbose_name='Amount')),
                ('declared_unit', models.CharField(choices=[('-', '-'), ('g', 'g'), ('mg', 'mg'), ('mcg', 'mcg'), ('kg', 'kg'), ('kcal', 'kcal'), ('IU', 'IU'), ('%', '%')], default='-', help_text='Unit the printed label used, kept so it can be shown again.', max_length=10, verbose_name='Declared Unit')),
                ('active', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='label_amounts', to='core.active', verbose_name='Active')),
                ('nutrition_facts', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='actives', to='core.nutritionfacts')),
            ],
            options={
                'verbose_name': 'Nutrition Active',
                'verbose_name_plural': 'Nutrition Actives',
                'constraints': [models.UniqueConstraint(fields=('nutrition_facts', 'active'), name='unique_nutrient_per_facts')],
            },
        ),
        migrations.CreateModel(
            name='ProductActive',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, editable=False, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('fraction', models.DecimalField(decimal_places=8, help_text='Mass of the active per unit of product mass.', max_digits=12, verbose_name='Mass Fraction')),
                ('active', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='product_amounts', to='core.active', verbose_name='Active')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='actives', to='core.product', verbose_name='Product')),
            ],
            options={
                'verbose_name': 'Product Active',
                'verbose_name_plural': 'Product Actives',
                'ordering': ('product__name', 'active__name'),
                'indexes': [models.Index(fields=['active', 'fraction'], name='core_produc_active__d94223_idx')],
                'constraints': [models.UniqueConstraint(fields=('product', 'active'), name='unique_product_active')],
            },
        ),
        migrations.CreateModel(
            name='ProductComponent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, editable=False, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('quantity', models.PositiveIntegerField(default=1, verbose_name='Quantity')),
                ('component', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='parent_links', to='core.product', verbose_name='Component')),
                ('parent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='component_links', to='core.product', verbose_name='Combo')),
            ],
            options={
                'verbose_name': 'Component',
                'verbose_name_plural': 'Components',
                'constraints': [models.UniqueConstraint(fields=('parent', 'component'), name='unique_product_component'), models.CheckConstraint(condition=models.Q(('parent', models.F('component')), _negated=True), name='product_component_not_self')],
            },
        ),
        migrations.CreateModel(
            name='ProductNutrition',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, editable=False, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('flavors', models.ManyToManyField(blank=True, to='core.flavor', verbose_name='Flavors')),
                ('nutrition_facts', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='product_profiles', to='core.nutritionfacts', verbose_name='Nutrition Facts')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='nutrition_profiles', to='core.product', verbose_name='Base Product')),
            ],
            options={
                'verbose_name': 'Product Nutrition Profile',
                'verbose_name_plural': 'Product Nutrition Profiles',
                'constraints': [models.UniqueConstraint(fields=('product', 'nutrition_facts'), name='unique_product_nutrition_facts')],
            },
        ),
        migrations.AddIndex(
            model_name='productstore',
            index=models.Index(fields=['store', 'product'], name='core_produc_store_i_e5d0b4_idx'),
        ),
        migrations.AddConstraint(
            model_name='productstore',
            constraint=models.UniqueConstraint(fields=('product', 'store'), name='unique_product_store'),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['name'], name='core_produc_name_be3252_idx'),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['brand', 'name'], name='core_produc_brand_i_8b60c4_idx'),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['kind'], name='core_produc_kind_1a67cf_idx'),
        ),
        migrations.RunPython(seed_label_actives, drop_label_actives),
    ]
