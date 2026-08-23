import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from laptop_market_scraper.models import (
    SearchCategory,
    SearchPage,
    SearchProduct,
    SearchSeed,
)
from laptop_market_scraper.parsers.search_api import (
    SearchGraphQLError,
    SearchSchemaError,
    parse_search_response,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "search_api"


def test_search_seed_validation():
    seed = SearchSeed(query="laptop", kind="generic")
    assert seed.query == "laptop"
    assert seed.kind == "generic"
    assert seed.brand_hint is None
    assert seed.max_pages == 20

    seed_brand = SearchSeed(query="asus laptop", kind="brand", brand_hint="asus", max_pages=5)
    assert seed_brand.brand_hint == "asus"
    assert seed_brand.max_pages == 5

    with pytest.raises(ValidationError):
        SearchSeed(query="laptop", kind="invalid_kind")

    with pytest.raises(ValidationError):
        SearchSeed(query="laptop", kind="generic", max_pages=0)


def test_search_category_defaults():
    cat = SearchCategory()
    assert cat.id is None
    assert cat.old_id is None
    assert cat.name is None
    assert cat.breadcrumb is None
    assert cat.ga_key is None

    cat_custom = SearchCategory(
        id="28",
        old_id=28,
        name="Laptop",
        breadcrumb="Komputer & Laptop > Laptop",
        ga_key="/search - product - category",
    )
    assert cat_custom.id == "28"
    assert cat_custom.old_id == 28
    assert cat_custom.name == "Laptop"


def test_search_product_instantiation_and_defaults():
    prod = SearchProduct(
        product_id="12345",
        name="ASUS Vivobook 14",
        url="https://www.tokopedia.com/asus/vivobook-14",
    )
    assert prod.product_id == "12345"
    assert prod.name == "ASUS Vivobook 14"
    assert prod.url == "https://www.tokopedia.com/asus/vivobook-14"
    assert prod.price is None
    assert prod.original_price_raw is None
    assert prod.discount_percent is None
    assert prod.shop_id is None
    assert prod.shop_name is None
    assert prod.shop_city is None
    assert prod.rating is None
    assert prod.stock is None
    assert isinstance(prod.category, SearchCategory)
    assert prod.raw == {}

    # Required fields missing
    with pytest.raises(ValidationError):
        SearchProduct(name="Missing ID", url="https://example.com")


def test_search_page_tuple_and_serialization():
    cat = SearchCategory(id="28", name="Laptop")
    prod1 = SearchProduct(
        product_id="101",
        name="Laptop A",
        url="https://tokopedia.com/a",
        price=10000000,
        category=cat,
        raw={"id": "101"},
    )
    prod2 = SearchProduct(
        product_id="102",
        name="Laptop B",
        url="https://tokopedia.com/b",
        price=15000000,
        category=cat,
        raw={"id": "102"},
    )

    page = SearchPage(
        query="laptop",
        page=1,
        rows=60,
        products=[prod1, prod2],
        total_data=120,
    )

    assert page.query == "laptop"
    assert page.page == 1
    assert page.rows == 60
    assert page.total_data == 120
    assert isinstance(page.products, tuple)
    assert len(page.products) == 2
    assert page.products[0].product_id == "101"

    # Test serialization
    dumped = page.model_dump()
    assert dumped["query"] == "laptop"
    assert len(dumped["products"]) == 2
    assert dumped["products"][0]["category"]["name"] == "Laptop"

    json_str = page.model_dump_json()
    assert "Laptop A" in json_str


def test_parse_search_response_page_1():
    with open(FIXTURES_DIR / "page_1.json", encoding="utf-8") as f:
        payload = json.load(f)

    result = parse_search_response(payload, query="laptop", page=1, rows=60)
    assert isinstance(result, SearchPage)
    assert result.query == "laptop"
    assert result.page == 1
    assert result.rows == 60
    assert result.total_data == 1038718
    assert len(result.products) == 60

    p0 = result.products[0]
    assert p0.product_id == "103564801973"
    assert "Kimiso Converter" in p0.name
    assert p0.url.startswith("https://www.tokopedia.com/")
    assert p0.price == 60000
    assert p0.original_price_raw == "Rp120.000"
    assert p0.discount_percent == 0.0
    assert p0.shop_id == "7494602698326443630"
    assert p0.shop_name == "KIMSTORE SPEAKER"
    assert p0.shop_city == "Kab. Tangerang"
    assert p0.rating == 5.0
    assert p0.category.name == "Komputer & Laptop"
    assert p0.category.id == "297"
    assert p0.category.old_id == 297
    assert p0.category.breadcrumb == "komputer-laptop/aksesoris-komputer-laptop/lainnya"
    assert p0.category.ga_key == "komputer-laptop/aksesoris-komputer-laptop/lainnya"
    assert p0.raw["id"] == "103564801973"


def test_parse_search_response_page_2():
    with open(FIXTURES_DIR / "page_2.json", encoding="utf-8") as f:
        payload = json.load(f)

    result = parse_search_response(payload, query="laptop", page=2, rows=60)
    assert isinstance(result, SearchPage)
    assert result.query == "laptop"
    assert result.page == 2
    assert result.rows == 60
    assert result.total_data == 1038716
    assert len(result.products) == 60


def test_parse_search_response_dict_payload():
    with open(FIXTURES_DIR / "page_1.json", encoding="utf-8") as f:
        list_payload = json.load(f)

    dict_payload = list_payload[0]
    result = parse_search_response(dict_payload, query="laptop", page=1, rows=60)
    assert len(result.products) == 60


def test_parse_search_response_query_alias():
    with open(FIXTURES_DIR / "page_1.json", encoding="utf-8") as f:
        list_payload = json.load(f)

    dict_payload = list_payload[0]
    # Replace searchProductV5 key with SearchProductV5Query
    search_data = dict_payload["data"].pop("searchProductV5")
    dict_payload["data"]["SearchProductV5Query"] = search_data

    result = parse_search_response(dict_payload, query="laptop", page=1, rows=60)
    assert len(result.products) == 60


def test_parse_search_response_graphql_error():
    error_payload = [{"errors": [{"message": "Unauthorized access"}]}]
    with pytest.raises(SearchGraphQLError, match="Unauthorized access"):
        parse_search_response(error_payload, query="laptop", page=1)

    error_payload_dict = {"errors": [{"message": "Invalid token"}]}
    with pytest.raises(SearchGraphQLError, match="Invalid token"):
        parse_search_response(error_payload_dict, query="laptop", page=1)


def test_parse_search_response_schema_error():
    with pytest.raises(SearchSchemaError):
        parse_search_response({}, query="laptop", page=1)

    with pytest.raises(SearchSchemaError):
        parse_search_response({"data": {}}, query="laptop", page=1)

    with pytest.raises(SearchSchemaError):
        parse_search_response({"data": {"searchProductV5": {}}}, query="laptop", page=1)

    with pytest.raises(SearchSchemaError):
        parse_search_response([], query="laptop", page=1)


def test_parse_search_response_empty_products():
    empty_payload = {
        "data": {
            "searchProductV5": {
                "header": {"totalData": 0},
                "data": {"products": []},
            }
        }
    }
    result = parse_search_response(empty_payload, query="laptop", page=1, rows=60)
    assert isinstance(result, SearchPage)
    assert result.total_data == 0
    assert result.products == ()

