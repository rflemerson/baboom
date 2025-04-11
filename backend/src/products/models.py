from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

class Brand(models.Model):
    short_name = models.CharField(max_length=100, unique=True)
    full_name = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.short_name

    class Meta:
        verbose_name = "Brand"
        verbose_name_plural = "Brands"


class ProteinType(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Protein Type"
        verbose_name_plural = "Protein Types"


class Product(models.Model):
    ORIGIN_CHOICES = [
        ('A', 'Animal'),
        ('V', 'Plant'),
        ('M', 'Mixed'),
    ]

    PACKAGING_CHOICES = [
        ('R', 'Refill'),
        ('C', 'Container'),
    ]

    PROCESSING_CHOICES = [
        ('I', 'Isolate'),
        ('C', 'Concentrate'),
        ('H', 'Hydrolyzed'),
    ]

    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=200)
    protein_types = models.ManyToManyField(ProteinType, related_name='products')
    weight = models.PositiveIntegerField(help_text="Total weight in grams")
    protein_concentration = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Protein percentage (1-100)"
    )
    origin = models.CharField(max_length=1, choices=ORIGIN_CHOICES)
    packaging = models.CharField(max_length=1, choices=PACKAGING_CHOICES)
    processing_type = models.CharField(
        max_length=1, 
        choices=PROCESSING_CHOICES, 
        blank=True, 
        null=True,
        help_text="Only for animal proteins"
    )

    @property
    def total_protein(self):
        return (self.weight * self.protein_concentration) / 100

    def __str__(self):
        return f"{self.brand} - {self.name}"

    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
        unique_together = ['brand', 'name']


class Store(models.Model):
    name = models.CharField(max_length=100, unique=True)
    website = models.URLField()
    country = models.CharField(max_length=50)
    logo_url = models.URLField(blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Store"
        verbose_name_plural = "Stores"


class PriceStock(models.Model):
    CURRENCY_CHOICES = [
        ('BRL', 'Brazilian Real'),
    ]

    STOCK_STATUS_CHOICES = [
        ('A', 'Available'),
        ('O', 'Out of Stock'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='prices')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='prices')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='BRL')
    stock_status = models.CharField(max_length=1, choices=STOCK_STATUS_CHOICES, default='A')
    valid_from = models.DateTimeField(auto_now_add=True)
    valid_to = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.product} - {self.store}: {self.currency} {self.price}"

    class Meta:
        verbose_name = "Price & Stock"
        verbose_name_plural = "Prices & Stock"
        ordering = ['-valid_from']
        indexes = [
            models.Index(fields=['product', 'store']),
        ]