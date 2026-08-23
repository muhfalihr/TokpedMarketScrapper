
from laptop_market_scraper.audit.models import FeatureRegistryEntry, ReliabilityStatus
from laptop_market_scraper.audit.registry import (
    CANDIDATE_FEATURES,
    FEATURE_REGISTRY,
    get_feature_registry_entry,
    list_features_by_dimension,
)


def test_reliability_status_enum_values():
    assert ReliabilityStatus.VERIFIED_EXACT == "VERIFIED_EXACT"
    assert ReliabilityStatus.VERIFIED_APPROXIMATE == "VERIFIED_APPROXIMATE"
    assert ReliabilityStatus.CONTEXT_DEPENDENT == "CONTEXT_DEPENDENT"
    assert ReliabilityStatus.SEMANTICS_UNVERIFIED == "SEMANTICS_UNVERIFIED"
    assert ReliabilityStatus.UNAVAILABLE == "UNAVAILABLE"


def test_candidate_features_tuple():
    expected = (
        "price",
        "original_price",
        "discount_percent",
        "sold_count",
        "view_count",
        "review_count",
        "rating",
        "talk_count",
        "transaction_success",
        "transaction_reject",
    )
    assert CANDIDATE_FEATURES == expected
    assert len(CANDIDATE_FEATURES) == 10


def test_feature_registry_completeness_and_structure():
    assert len(FEATURE_REGISTRY) == 10
    for feature in CANDIDATE_FEATURES:
        assert feature in FEATURE_REGISTRY
        entry = FEATURE_REGISTRY[feature]
        assert isinstance(entry, FeatureRegistryEntry)
        assert entry.feature_name == feature
        assert entry.research_dimension in {"Pricing", "Demand", "Engagement", "Perception"}


def test_specific_feature_registry_entries():
    price_entry = FEATURE_REGISTRY["price"]
    assert price_entry.research_dimension == "Pricing"
    assert price_entry.nullable is False
    assert price_entry.default_reliability == ReliabilityStatus.VERIFIED_EXACT

    orig_price_entry = FEATURE_REGISTRY["original_price"]
    assert orig_price_entry.research_dimension == "Pricing"
    assert orig_price_entry.nullable is True
    assert orig_price_entry.default_reliability == ReliabilityStatus.CONTEXT_DEPENDENT

    sold_entry = FEATURE_REGISTRY["sold_count"]
    assert sold_entry.research_dimension == "Demand"
    assert sold_entry.nullable is True
    assert sold_entry.default_reliability == ReliabilityStatus.VERIFIED_APPROXIMATE

    tx_success = FEATURE_REGISTRY["transaction_success"]
    assert tx_success.research_dimension == "Demand"
    assert tx_success.nullable is True
    assert tx_success.default_reliability == ReliabilityStatus.SEMANTICS_UNVERIFIED

    tx_reject = FEATURE_REGISTRY["transaction_reject"]
    assert tx_reject.research_dimension == "Demand"
    assert tx_reject.nullable is True
    assert tx_reject.default_reliability == ReliabilityStatus.SEMANTICS_UNVERIFIED


def test_get_feature_registry_entry():
    entry = get_feature_registry_entry("rating")
    assert entry is not None
    assert entry.feature_name == "rating"
    assert entry.research_dimension == "Perception"

    missing = get_feature_registry_entry("non_existent_feature")
    assert missing is None


def test_list_features_by_dimension():
    pricing_features = list_features_by_dimension("Pricing")
    pricing_names = [e.feature_name for e in pricing_features]
    assert set(pricing_names) == {"price", "original_price", "discount_percent"}

    demand_features = list_features_by_dimension("Demand")
    demand_names = [e.feature_name for e in demand_features]
    assert set(demand_names) == {"sold_count", "view_count", "transaction_success", "transaction_reject"}

    engagement_features = list_features_by_dimension("Engagement")
    engagement_names = [e.feature_name for e in engagement_features]
    assert set(engagement_names) == {"review_count", "talk_count"}

    perception_features = list_features_by_dimension("Perception")
    perception_names = [e.feature_name for e in perception_features]
    assert set(perception_names) == {"rating"}

    empty_features = list_features_by_dimension("NonExistentDimension")
    assert empty_features == []
