import pandas as pd
import pytest

from tokped_market_scrapper.ml_readiness import (
    AssociationConfig,
    ExtremesConfig,
    MLReadinessConfig,
    ReadinessDataset,
    RepresentationConfig,
    detect_extreme_prices,
)


@pytest.fixture
def sample_config() -> MLReadinessConfig:
    return MLReadinessConfig(
        features=["price", "rating", "review_count"],
        representations={
            "r1": RepresentationConfig(
                id="r1", description="R1", features=["price", "rating"]
            ),
        },
        extremes=ExtremesConfig(
            price_lower_quantile=0.01,
            price_upper_quantile=0.99,
            iqr_multiplier=1.5,
            robust_z_threshold=3.5,
            sample_limit=20,
        ),
        association=AssociationConfig(spearman_redundancy_threshold=0.85),
    )


def make_dataset(
    products_df: pd.DataFrame,
    raw_by_listing_key: dict | None = None,
    provenance_df: pd.DataFrame | None = None,
) -> ReadinessDataset:
    return ReadinessDataset(
        products=products_df,
        provenance=provenance_df if provenance_df is not None else pd.DataFrame(),
        discoveries=pd.DataFrame(),
        raw_by_listing_key=raw_by_listing_key if raw_by_listing_key is not None else {},
    )


def make_price_frame() -> pd.DataFrame:
    # 100 laptops with realistic prices between 10M and 20M
    prices = [10_000_000.0 + i * 100_000.0 for i in range(100)]
    rows = [
        {
            "listing_key": f"key_{i:03d}",
            "product_name": f"Laptop {i:03d}",
            "product_url": f"https://tokopedia.com/laptop-{i:03d}",
            "price": prices[i],
            "breadcrumb": "Computers & Laptops",
            "shop_name": "TechStore",
        }
        for i in range(100)
    ]
    return pd.DataFrame(rows)


def test_detect_extreme_prices_flags_low_and_high_extremes(sample_config):
    frame = make_price_frame()
    # Add a low extreme (Rp 3.600) and high extreme (Rp 189.999.008)
    low_extreme = {
        "listing_key": "low_ext",
        "product_name": "Low Price Laptop Accessory/Typo",
        "product_url": "https://tokopedia.com/low",
        "price": 3600.0,
        "breadcrumb": "Accessories",
        "shop_name": "CheapStore",
    }
    high_extreme = {
        "listing_key": "high_ext",
        "product_name": "Ultra Supercomputer Extreme",
        "product_url": "https://tokopedia.com/high",
        "price": 189_999_008.0,
        "breadcrumb": "Servers",
        "shop_name": "EnterpriseStore",
    }
    frame = pd.concat([frame, pd.DataFrame([low_extreme, high_extreme])], ignore_index=True)

    dataset = make_dataset(frame)
    observations = detect_extreme_prices(dataset, config=sample_config)

    assert isinstance(observations, tuple)
    flagged_keys = {obs.listing_key for obs in observations}
    assert "low_ext" in flagged_keys
    assert "high_ext" in flagged_keys

    obs_low = next(o for o in observations if o.listing_key == "low_ext")
    assert obs_low.price == 3600.0
    assert obs_low.lower_quantile_flag is True
    assert obs_low.iqr_flag is True
    assert "lower_quantile" in obs_low.trigger_names
    assert "iqr" in obs_low.trigger_names
    assert obs_low.review_status == "UNREVIEWED"

    obs_high = next(o for o in observations if o.listing_key == "high_ext")
    assert obs_high.price == 189_999_008.0
    assert obs_high.upper_quantile_flag is True
    assert obs_high.iqr_flag is True
    assert "upper_quantile" in obs_high.trigger_names
    assert "iqr" in obs_high.trigger_names


def test_extreme_price_is_flagged_but_not_removed(sample_config):
    frame = pd.DataFrame(
        [
            {"listing_key": "a", "price": 10_000_000.0},
            {"listing_key": "b", "price": 11_000_000.0},
            {"listing_key": "c", "price": 12_000_000.0},
            {"listing_key": "extreme", "price": 190_000_000.0},
        ]
    )
    dataset = make_dataset(frame)
    observations = detect_extreme_prices(dataset, config=sample_config)

    assert any(item.listing_key == "extreme" for item in observations)
    assert len(dataset.products) == 4


def test_extreme_audit_does_not_mutate_source_frame(sample_config):
    frame = make_price_frame()
    original = frame.copy(deep=True)

    dataset = make_dataset(frame)
    detect_extreme_prices(dataset, config=sample_config)

    pd.testing.assert_frame_equal(dataset.products, original)


def test_robust_z_score_calculation(sample_config):
    # Dataset with non-zero MAD
    prices = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 100.0]
    frame = pd.DataFrame([{"listing_key": f"k{i}", "price": p} for i, p in enumerate(prices)])

    dataset = make_dataset(frame)
    observations = detect_extreme_prices(dataset, config=sample_config)

    obs_high = next((o for o in observations if o.listing_key == "k9"), None)
    assert obs_high is not None
    # median = 13.5, MAD = median(|x - 13.5|)
    # |x - 13.5| = [3.5, 2.5, 1.5, 0.5, 0.5, 1.5, 2.5, 3.5, 4.5, 86.5] -> sorted: [0.5, 0.5, 1.5, 1.5, 2.5, 2.5, 3.5, 3.5, 4.5, 86.5]
    # MAD = (2.5 + 2.5) / 2 = 2.5
    # robust_z = 0.6745 * (100 - 13.5) / 2.5 = 0.6745 * 86.5 / 2.5 = 23.3377
    assert obs_high.robust_z_score is not None
    assert obs_high.robust_z_score > 3.5
    assert obs_high.robust_z_flag is True
    assert "robust_z" in obs_high.trigger_names


def test_zero_mad_fallback(sample_config):
    # >50% identical prices -> MAD is 0.0
    prices = [10_000_000.0] * 8 + [50_000_000.0, 100_000_000.0]
    frame = pd.DataFrame([{"listing_key": f"k{i}", "price": p} for i, p in enumerate(prices)])

    dataset = make_dataset(frame)
    observations = detect_extreme_prices(dataset, config=sample_config)

    for obs in observations:
        # Since MAD is 0, robust_z_score must be None and robust_z_flag False
        assert obs.robust_z_score is None
        assert obs.robust_z_flag is False
        assert "robust_z" not in obs.trigger_names


def test_queue_deterministic_sorting(sample_config):
    # Setup observations with different trigger counts, robust_z, price, listing_key
    frame = pd.DataFrame(
        [
            {"listing_key": "key_b", "price": 2000.0},
            {"listing_key": "key_a", "price": 1000.0},
        ]
        + [{"listing_key": f"norm_{i}", "price": 500.0} for i in range(20)]
    )

    dataset = make_dataset(frame)
    observations = detect_extreme_prices(dataset, config=sample_config)

    # Verify order is deterministic and matches:
    # 1. len(trigger_names) DESC
    # 2. abs(robust_z_score) DESC (None -> -1.0)
    # 3. price ASC
    # 4. listing_key ASC
    for i in range(len(observations) - 1):
        o1 = observations[i]
        o2 = observations[i + 1]

        t1 = len(o1.trigger_names)
        t2 = len(o2.trigger_names)
        assert t1 >= t2

        if t1 == t2:
            z1 = abs(o1.robust_z_score) if o1.robust_z_score is not None else -1.0
            z2 = abs(o2.robust_z_score) if o2.robust_z_score is not None else -1.0
            assert z1 >= z2

            if z1 == z2:
                assert o1.price <= o2.price
                if o1.price == o2.price:
                    assert o1.listing_key <= o2.listing_key


def test_extract_raw_price_and_source(sample_config):
    frame = make_price_frame()
    extreme_row = pd.DataFrame([{"listing_key": "item_1", "price": 189_999_008.0}])
    frame = pd.concat([frame, extreme_row], ignore_index=True)
    prov_frame = pd.DataFrame(
        [
            {
                "listing_key": "item_1",
                "feature_name": "price",
                "source_layer": "graphql_search",
                "source_field": "price_int",
                "raw_value_json": "189999008",
            }
        ]
    )
    raw_payloads = {
        "item_1": {
            "listing_key": "item_1",
            "price": "Rp189.999.008",
        }
    }

    dataset = make_dataset(frame, raw_by_listing_key=raw_payloads, provenance_df=prov_frame)
    observations = detect_extreme_prices(dataset, config=sample_config)

    obs = next(o for o in observations if o.listing_key == "item_1")
    assert obs.raw_price_value in ("189999008", 189999008)
    assert obs.price_source == "graphql_search"



def test_empty_dataset(sample_config):
    empty_frame = pd.DataFrame(columns=["listing_key", "price"])
    dataset = make_dataset(empty_frame)
    observations = detect_extreme_prices(dataset, config=sample_config)
    assert observations == ()
