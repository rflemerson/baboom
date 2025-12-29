# Open Food Facts (OFF) Documentation

## Overview
Open Food Facts is a collaborative database of food products from around the world. It provides open data via API, bulk exports, and a Python SDK.

**Key Characteristics:**
- **License**: Open Database License (ODbL).
    - **Attribution**: "Research using data from Open Food Facts". E.g., "Nutrition info from Open Food Facts".
    - **Share-Alike**: If you mix OFF data with other DBs, the result must be ODbL.
- **Focus**: Product metadata (ingredients, nutrition, labels, Nutri-Score, Eco-Score).
- **Limitations**: No pricing, no real-time stock, community-sourced (potential for errors).

## Data Reusability

### 1. Python SDK (`openfoodfacts`)
Official SDK for searching and retrieving individual product data. Best for "on-demand" enrichment.

**Installation:**
```bash
pip install openfoodfacts
```

**Usage (Search):**
```python
from openfoodfacts import API

# User-Agent is MANDATORY
api = API(user_agent="Baboom/1.0 (dev@baboom.com)", country="br")

# Text search
results = api.product.text_search("Whey Protein", page=1, page_size=5)
for product in results.get('products', []):
    print(product.get('product_name'))
    print(product.get('nutriments', {}).get('proteins_100g'))
```

**Usage (Get by Barcode - EAN):**
```python
code = "7898641073261" # Dux Nutrition Whey
product = api.product.get(code)
print(product.get('nutriscore_grade'))
```

### 2. Bulk Data Exports (Parquet)
For analytics or massive enrichment, avoid the API (rate limits) and use bulk exports.

- **Format**: Parquet (Column-oriented, optimized).
- **Hosted on**: [Hugging Face](https://huggingface.co/datasets/openfoodfacts/product-database).
- **Access via DuckDB**:
    ```bash
    duckdb :memory: "SELECT code, product_name, brands, nutriments FROM 'https://huggingface.co/datasets/openfoodfacts/product-database/resolve/main/food.parquet' WHERE categories LIKE '%supplements%' LIMIT 10;"
    ```

### 3. Mongo & CSV
- **MongoDB Dump**: Full daily dump (~30GB).
- **CSV/JSONL**: Daily snapsots available.

## Integration Strategy for Baboom

### Use Case: Data Enrichment
The Scrapers are the primary source of truth for **Price** and **Availability**. OFF should be used to:
1.  **Fill Gaps**: If a scraper fails to get nutrition info.
2.  **Validate Data**: Check if protein content matches.
3.  **Images**: Get better quality packaging photos.
4.  **Nutri-Score**: Display health score if available.

### Fallback Flow
1. Scraper fetches Product from Store (Price, Stock, Name).
2. If `protein_100g` is missing:
    - Search OFF by `EAN` (if available).
    - Search OFF by `Name` (fuzzy match).
3. Update Product record with enrichment data.

## API & Rate Limits
- **Authentication**: None (Session cookie for Writes).
- **Rate Limit**: ~100 req/min (Soft limit). Be nice.
- **User-Agent**: **Strictly required**. Requests without UA are blocked.
