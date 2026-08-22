import pytest
from pydantic import ValidationError

from laptop_market_scraper.models import (
    SearchCategory,
    SearchPage,
    SearchProduct,
    SearchSeed,
)


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
