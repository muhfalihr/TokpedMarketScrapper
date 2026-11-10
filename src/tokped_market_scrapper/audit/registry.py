from laptop_market_scraper.audit.models import FeatureRegistryEntry, ReliabilityStatus

CANDIDATE_FEATURES: tuple[str, ...] = (
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

FEATURE_REGISTRY: dict[str, FeatureRegistryEntry] = {
    "price": FeatureRegistryEntry(
        feature_name="price",
        research_dimension="Pricing",
        expected_dtype="float/int",
        nullable=False,
        semantic_description="Current selling price of the product listing in IDR.",
        known_semantic_limitations="May reflect active promotional campaigns or dynamic pricing discounts.",
        default_reliability=ReliabilityStatus.VERIFIED_EXACT,
    ),
    "original_price": FeatureRegistryEntry(
        feature_name="original_price",
        research_dimension="Pricing",
        expected_dtype="float/int",
        nullable=True,
        semantic_description="Strikethrough base price prior to discount application in IDR.",
        known_semantic_limitations="Present only when seller sets an explicit discount/slash price.",
        default_reliability=ReliabilityStatus.CONTEXT_DEPENDENT,
    ),
    "discount_percent": FeatureRegistryEntry(
        feature_name="discount_percent",
        research_dimension="Pricing",
        expected_dtype="float/int",
        nullable=True,
        semantic_description="Percentage discount relative to original price.",
        known_semantic_limitations="Null when no strikethrough price exists.",
        default_reliability=ReliabilityStatus.VERIFIED_EXACT,
    ),
    "sold_count": FeatureRegistryEntry(
        feature_name="sold_count",
        research_dimension="Demand",
        expected_dtype="int",
        nullable=True,
        semantic_description="Total units sold for this listing.",
        known_semantic_limitations="Parsed from formatted strings (e.g., '100+ rb', '1rb+') representing lower bounds.",
        default_reliability=ReliabilityStatus.VERIFIED_APPROXIMATE,
    ),
    "view_count": FeatureRegistryEntry(
        feature_name="view_count",
        research_dimension="Demand",
        expected_dtype="int",
        nullable=True,
        semantic_description="Total page views accumulated by product listing.",
        known_semantic_limitations="Aggregation latency may cause minor delays relative to real-time views.",
        default_reliability=ReliabilityStatus.VERIFIED_EXACT,
    ),
    "review_count": FeatureRegistryEntry(
        feature_name="review_count",
        research_dimension="Engagement",
        expected_dtype="int",
        nullable=False,
        semantic_description="Total count of user reviews submitted for product.",
        known_semantic_limitations="Reflects review count rather than total buyer satisfaction or order count.",
        default_reliability=ReliabilityStatus.VERIFIED_EXACT,
    ),
    "rating": FeatureRegistryEntry(
        feature_name="rating",
        research_dimension="Perception",
        expected_dtype="float",
        nullable=False,
        semantic_description="Average customer rating score (0.0 to 5.0).",
        known_semantic_limitations="Unrated listings default to 0.0 or null across different API representations.",
        default_reliability=ReliabilityStatus.VERIFIED_EXACT,
    ),
    "talk_count": FeatureRegistryEntry(
        feature_name="talk_count",
        research_dimension="Engagement",
        expected_dtype="int",
        nullable=True,
        semantic_description="Total buyer-seller discussion / talk messages.",
        known_semantic_limitations="May be omitted on newer API endpoints or inactive listings.",
        default_reliability=ReliabilityStatus.VERIFIED_EXACT,
    ),
    "transaction_success": FeatureRegistryEntry(
        feature_name="transaction_success",
        research_dimension="Demand",
        expected_dtype="int",
        nullable=True,
        semantic_description="Reported count of successful transactions.",
        known_semantic_limitations="Field semantics and source field mapping remain unverified in production payload audit.",
        default_reliability=ReliabilityStatus.SEMANTICS_UNVERIFIED,
    ),
    "transaction_reject": FeatureRegistryEntry(
        feature_name="transaction_reject",
        research_dimension="Demand",
        expected_dtype="int",
        nullable=True,
        semantic_description="Reported count of rejected or cancelled transactions.",
        known_semantic_limitations="Field semantics and source field mapping remain unverified in production payload audit.",
        default_reliability=ReliabilityStatus.SEMANTICS_UNVERIFIED,
    ),
}


def get_feature_registry_entry(name: str) -> FeatureRegistryEntry | None:
    """Retrieve feature registry entry by feature name."""
    return FEATURE_REGISTRY.get(name)


def list_features_by_dimension(dimension: str) -> list[FeatureRegistryEntry]:
    """List all feature registry entries belonging to a given research dimension."""
    return [entry for entry in FEATURE_REGISTRY.values() if entry.research_dimension == dimension]
