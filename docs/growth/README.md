# Growth Supplements API Strategy (Wap.Store)

## 1. Overview
**Platform Identified:** [Wap.Store](https://www.wapstore.com.br/) (V2 API)
**Base URL:** `https://www.gsuplementos.com.br/api/v2/front`
**Protocol:** REST / JSON
**Authentication:** Public App Token (`wapstore`)
**Security:** Requires specific User-Agent headers and ignoring SSL verification (`verify=False`) to bypass Sucuri WAF when using Python.

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
> [!WARNING]
> You **MUST** disable SSL verification (`verify=False` in Python/Requests) or use a specific cipher suite. The server (protected by Sucuri) often rejects standard Python OpenSSL handshakes.

**Python Example:**
```python
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
requests.get(url, headers=headers, verify=False)
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
      "label": "Proteínas",
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

We have implemented `GrowthApiSpider` using this strategy:
1.  **Session**: Use `requests.Session()` with `verify=False`.
2.  **Pagination**: Loop with `offset += 30` until `len(items) < 30`.
3.  **Parsing**: robustly check for `data['conteudo']['produtos']` as the API might return structural JSON without products if params are wrong.

## 5. Known Limitations
-   **Limit**: Strict maximum of 30 items.
-   **WAF**: Highly sensitive to User-Agent changes. Stick to "insomnia/12.2.0" or Chrome High-Ver.
