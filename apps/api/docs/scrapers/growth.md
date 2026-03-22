# Growth Supplements API Strategy (Wap.Store)

## 1. Overview
**Platform Identified:** [Wap.Store](https://www.wapstore.com.br/) (V2 API)
**Base URL:** `https://www.gsuplementos.com.br/api/v2/front`
**Protocol:** REST / JSON
**Authentication:** Public App Token (`wapstore`)
**Security:** Requires specific headers; SSL verification behavior is configurable in spider via `GROWTH_SSL_VERIFY` (default `0`, i.e., `verify=False`).

## 2. Critical Configuration

### Headers
To successfully consume this API, every request MUST include the following headers. Failure to include them (especially `app-token`) results in 401/403 errors.

```json
{
  "app-token": "wapstore",
  "User-Agent": "insomnia/12.2.0",
  "Content-Type": "application/json",
  "accept": "application/json, text/plain, */*"
}
```

### SSL Verification
Default behavior uses `verify=False` because Sucuri may reject standard Python TLS handshakes.
Set `GROWTH_SSL_VERIFY=1` to enforce certificate verification in stricter environments.

**Python Example:**
```python
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
requests.get(url, headers=headers, verify=False)  # default
# requests.get(url, headers=headers, verify=True)  # with GROWTH_SSL_VERIFY=1
```

## 3. Endpoints

### A. Listing Categories (Menus)
Retrieve the full category tree and dynamic URLs.

-   **URL:** `/struct/menus/nova-home-suplementos-categorias`
-   **Method:** `GET`
-   **Purpose:** Discovery of category slugs (e.g., `/proteina/`, `/creatina/`).

**Response Snippet:**
```json
{
  "id": 24,
  "nome": "ESCOLHA SEU SUPLEMENTO POR CATEGORIA",
  "menu": [
    {
      "label": "Proteins",
      "link": "https://www.gsuplementos.com.br/proteina",
      "target": "_self"
    }
  ]
}
```

### B. Product Listing
Fetch products for a specific category slug.

-   **URL:** `/url/product/listing/category`
-   **Method:** `GET`
-   **Parameters:**
    -   `url`: The category slug (e.g., `/proteina/`, `/vegano/`).
    -   `offset`: Pagination offset (0, 30, 60...).
    -   `limit`: Items per page (**Max 30**). Setting > 30 returns HTTP 400.

**cURL Example:**
```bash
curl --request GET \
  --url 'https://www.gsuplementos.com.br/api/v2/front/url/product/listing/category?url=/proteina/&offset=0&limit=30' \
  --header 'app-token: wapstore' \
  --header 'User-Agent: insomnia/12.2.0' \
  --insecure
```

**Response Structure:**
The product data is nested deep within `conteudo.produtos`.

```json
{
  "conteudo": {
    "produtos": [
      {
        "id": 9934,
        "nome": "Top Whey Protein (1kg)",
        "link": "top-whey-protein-concentrado-1kg-growth-supplements-p985936",
        "precos": {
           "vista": 139.50,
           "por": 139.50
        },
        "estoque": 100
      }
    ]
  }
}
```

### C. Verify URL
Check if a URL slug is valid and mapped.

-   **URL:** `/url/verify`
-   **Method:** `GET`
-   **Parameters:** `url=/proteina/`
-   **Response:** `{"nivel":"product/listing/category"}` (Confirms mapping).

## 4. Implementation Strategy (Python)

We have implemented `GrowthSpider` using this strategy:
1.  **HTTP Client**: Use shared client with configurable `verify` (`GROWTH_SSL_VERIFY`).
2.  **Pagination**: Loop with `offset += 30` until `len(items) < 30`.
3.  **Parsing**: robustly check `conteudo.produtos` and `data.list`.
4.  **Validation**: require valid URL and parseable price before persisting item.
5.  **Stock Logic**: unknown stock keeps item as available (avoids false out-of-stock).
6.  **Context Persistence**: save the API-derived product JSON in
    `ScrapedPage.api_context` and the HTML-derived structured metadata in
    `ScrapedPage.html_structured_data`.

## 5. Known Limitations
-   **Limit**: Strict maximum of 30 items.
-   **WAF**: Highly sensitive to User-Agent changes. Stick to "insomnia/12.2.0" or Chrome High-Ver.
