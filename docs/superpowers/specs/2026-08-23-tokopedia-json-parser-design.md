# Tokopedia JSON State Parser Design

## 1. Context and Problem
The current implementation of the Tokopedia Laptop Scraper relies on standard HTML parsing (looking for `<a>` tags) to extract product links and next-page pagination URLs. However, modern Tokopedia search pages are Client-Side Rendered (CSR). The raw HTML served to HTTP clients contains only a skeleton and a hidden `<script>` tag with the full application state (JSON). Consequently, the HTTP-only scraper yields zero results.

To maintain the high performance and scalability required by the project (Option A), we must extract this JSON state instead of relying on a slow, resource-intensive headless browser (Patchright) fallback.

## 2. Architecture & Components
We will modify the core listing parser `src/laptop_market_scraper/parsers/listing.py` to extract and parse the JSON state.

### 2.1 JSON Extraction (`extract_product_links`)
*   **Target:** `extract_product_links(response: Response) -> list[str]`
*   **Mechanism:** 
    *   Search `response.text` for the known global state variables injected by Tokopedia (e.g., `window.__INITIAL_STATE__`, Next.js `__NEXT_DATA__`, or similar script blocks).
    *   Use Regular Expressions (Regex) to isolate the JSON string payload.
    *   Parse the string into a Python dictionary.
*   **Data Traversal:**
    *   Navigate the JSON dictionary (using safe `.get()` methods or dictionary traversal) to locate the `products` array.
    *   Iterate over the products and extract the `url` property.
    *   Normalize or clean the URLs if necessary (e.g., stripping tracking parameters) before yielding.
*   **Fallback:** If the JSON structure cannot be found or parsed, log a warning and fall back to the existing DOM-based `a[href]` extraction (graceful degradation).

### 2.2 Pagination Extraction (`extract_next_page`)
*   **Target:** `extract_next_page(response: Response) -> str | None`
*   **Mechanism:**
    *   Parse the same JSON state used in the product extraction.
    *   Locate the pagination metadata (e.g., `hasNextPage`, `totalData`).
*   **URL Construction:** 
    *   If a next page is indicated, construct the next URL by incrementing the `page` query parameter of the current `response.url`.

## 3. Data Flow
1.  **Spider** (`TokopediaLaptopSpider`) fetches the search listing URL.
2.  **Spider** passes the raw `Response` to `extract_product_links`.
3.  **Listing Parser** isolates the JSON string, parses it, and extracts product URLs.
4.  **Spider** calls `extract_next_page` to check for JSON pagination flags.
5.  **Spider** yields the next search page request.

## 4. Error Handling
*   **Missing State:** If the script tag is not found, log a debug/warning message and return an empty list/None, falling back to DOM parsing.
*   **Malformed JSON:** Catch `json.JSONDecodeError` to prevent the scraper from crashing if Tokopedia serves malformed data.
*   **Schema Changes:** Catch `KeyError` or use safe `.get()` chains, logging the structural change for future maintenance.

## 5. Testing Strategy
*   Update `tests/test_listing_parser.py` to include a fixture of Tokopedia's actual JSON state HTML structure.
*   Assert that `extract_product_links` can successfully pull URLs from the mock JSON.
*   Assert that `extract_next_page` correctly identifies the next page based on JSON pagination metadata.
