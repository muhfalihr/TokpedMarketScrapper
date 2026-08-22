import pytest

from laptop_market_scraper.eligibility import (
    ALLOWED_BREADCRUMB_EXACT,
    ALLOWED_BREADCRUMB_PREFIXES,
    EligibilityResult,
    evaluate_laptop_eligibility,
    is_laptop_candidate,
)
from laptop_market_scraper.models import SearchCategory, SearchProduct


@pytest.fixture
def product_factory():
    def _create(breadcrumb: str, name: str = "ASUS Vivobook 14", product_id: str = "123") -> SearchProduct:
        return SearchProduct(
            product_id=product_id,
            name=name,
            url="https://tokopedia.com/test/product",
            category=SearchCategory(breadcrumb=breadcrumb),
        )

    return _create


@pytest.mark.parametrize(
    "breadcrumb",
    [
        "komputer-laptop/laptop/laptop-consumer",
        "komputer-laptop/laptop/notebook",
        "komputer-laptop/laptop/ultrabook",
        "komputer-laptop/laptop/laptop-2-in-1",
        "komputer-laptop/laptop/macbook",
        "komputer-laptop/pc-laptop-gaming/laptop-gaming",
    ],
)
def test_accepts_laptop_breadcrumbs(product_factory, breadcrumb):
    product = product_factory(breadcrumb=breadcrumb, name="ASUS Vivobook 14 A1405ZA")
    result = evaluate_laptop_eligibility(product)
    assert isinstance(result, EligibilityResult)
    assert result.accepted is True
    assert "Eligible" in result.reason or result.reason != ""


@pytest.mark.parametrize(
    "breadcrumb",
    [
        "komputer-laptop/aksesoris-komputer-laptop/tas-laptop",
        "komputer-laptop/aksesoris-komputer-laptop/alas-laptop",
        "komputer-laptop/aksesoris-komputer-laptop/adaptor-laptop",
        "komputer-laptop/komponen-laptop/ram-laptop",
        "komputer-laptop/kabel-adaptor/usb-hub-extension",
        "komputer-laptop/media-penyimpanan-data/ssd",
        "fashion-pria/tas-pria/tas-ransel-pria",
    ],
)
def test_rejects_non_laptop_breadcrumbs(product_factory, breadcrumb):
    product = product_factory(breadcrumb=breadcrumb, name="Laptop Stand Holder")
    result = evaluate_laptop_eligibility(product)
    assert isinstance(result, EligibilityResult)
    assert result.accepted is False
    assert "not an allowed laptop category" in result.reason or "Breadcrumb" in result.reason


def test_title_without_laptop_word_accepted_if_breadcrumb_eligible(product_factory):
    # Title doesn't contain "laptop"
    product = product_factory(
        breadcrumb="komputer-laptop/laptop/laptop-consumer",
        name="ASUS Vivobook 14 OLED X1405ZA Core i5 16GB 512GB",
    )
    result = evaluate_laptop_eligibility(product)
    assert result.accepted is True


@pytest.mark.parametrize(
    "title",
    [
        "Tas Laptop Waterproof 14 Inch",
        "Charger Laptop ASUS 65W Original",
        "Adaptor Laptop Lenovo Type C",
        "Cooling Pad Laptop RGB Dual Fan",
        "Stand Laptop Aluminium Ergonomic Holder",
        "Sleeve Laptop 13 Inch Neoprene Case",
        "Skin Laptop Transparan Anti Gores",
        "Stiker Laptop Vinyl Aesthetic",
        "Casing Laptop HP Pavilion Bottom Case",
        "Keyboard Laptop Acer Aspire",
        "LCD Laptop ASUS Zenbook 14 LED",
        "Layar Laptop Dell Latitude",
        "Baterai Laptop HP Pavilion 14",
        "Battery Laptop ThinkPad T480",
        "Fan Laptop Cooling Fan Internal",
        "Engsel Laptop Hinge ASUS Vivobook",
    ],
)
def test_secondary_negative_title_guard(product_factory, title):
    # Even inside allowed breadcrumb, obvious accessories/parts must be rejected
    product = product_factory(
        breadcrumb="komputer-laptop/laptop/laptop-consumer",
        name=title,
    )
    result = evaluate_laptop_eligibility(product)
    assert result.accepted is False
    assert "accessory keyword" in result.reason.lower() or "title" in result.reason.lower()


def test_evaluate_laptop_eligibility_dict_input():
    product_dict = {
        "name": "Lenovo Legion Slim 5 16 APH8",
        "category": {
            "breadcrumb": "komputer-laptop/pc-laptop-gaming/laptop-gaming",
        },
    }
    result = evaluate_laptop_eligibility(product_dict)
    assert result.accepted is True

    bad_dict = {
        "name": "Charger Lenovo 65W",
        "category": {
            "breadcrumb": "komputer-laptop/aksesoris-komputer-laptop/adaptor-laptop",
        },
    }
    result_bad = evaluate_laptop_eligibility(bad_dict)
    assert result_bad.accepted is False


def test_is_laptop_candidate_backward_compatibility():
    assert is_laptop_candidate("ASUS Vivobook 14", ("komputer-laptop/laptop/laptop-consumer",)) is True
    assert is_laptop_candidate("Tas Laptop 14 Inch", ("komputer-laptop/laptop/laptop-consumer",)) is False
    assert is_laptop_candidate("Tas Laptop 14 Inch", ("komputer-laptop/aksesoris-komputer-laptop/tas-laptop",)) is False
