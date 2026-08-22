import pytest

from laptop_market_scraper.eligibility import is_laptop_candidate


@pytest.mark.parametrize(
    ("title", "breadcrumbs", "expected"),
    [
        ("ASUS Vivobook Laptop 14", (), True),
        ("Lenovo LOQ Gaming Notebook", (), True),
        ("Tas Laptop Waterproof 14 Inch", (), False),
        ("Charger Laptop ASUS 65W", (), False),
        ("Cooling Pad Laptop RGB", (), False),
        ("MacBook Air M4", ("Komputer", "Laptop"), True),
        ("Ultrabook Dell XPS 13", (), True),
        ("Chromebook Acer Spin", (), True),
        ("Sleeve Laptop 13 Inch Neoprene", (), False),
        ("Adaptor Laptop Lenovo 45W", (), False),
        ("Adapter Laptop Dell", (), False),
        ("Stand Laptop Aluminium Ergonomic", (), False),
        ("Baterai Laptop HP Pavilion", (), False),
        ("Battery Laptop Thinkpad", (), False),
        ("Screen Protector Laptop 15.6", (), False),
        ("LCD Laptop ASUS Zenbook", (), False),
        ("Keyboard Laptop Acer", (), False),
        ("Mouse Laptop Wireless", (), False),
        ("Casing Laptop HP", (), False),
        ("Random Phone Case", (), False),
        ("Apple MacBook Pro 16 M3 Max", ("Komputer & Laptop", "Laptop", "Laptop Gaming"), True),
    ],
)
def test_laptop_eligibility(title, breadcrumbs, expected):
    assert is_laptop_candidate(title, breadcrumbs) is expected
