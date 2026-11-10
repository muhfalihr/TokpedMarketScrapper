import json
from collections.abc import Mapping
from typing import Any

import pandas as pd

from tokped_market_scrapper.ml_readiness.loader import ReadinessDataset
from tokped_market_scrapper.ml_readiness.models import (
    ExtremePriceObservation,
    MLReadinessConfig,
)


def _extract_raw_price_info(
    listing_key: str,
    provenance_df: pd.DataFrame,
    raw_by_listing_key: Mapping[str, dict[str, Any]],
) -> tuple[str | int | float | None, str | None]:
    raw_price_val: str | int | float | None = None
    price_source: str | None = None

    if (
        not provenance_df.empty
        and "listing_key" in provenance_df.columns
        and "feature_name" in provenance_df.columns
    ):
        match = provenance_df[
            (provenance_df["listing_key"].astype(str) == listing_key)
            & (provenance_df["feature_name"] == "price")
        ]
        if not match.empty:
            row = match.iloc[0]
            if "source_layer" in row and pd.notna(row["source_layer"]):
                price_source = str(row["source_layer"])

            if "raw_value_json" in row and pd.notna(row["raw_value_json"]):
                val_str = str(row["raw_value_json"])
                try:
                    raw_price_val = json.loads(val_str)
                except (json.JSONDecodeError, TypeError, ValueError):
                    raw_price_val = val_str
            elif "raw_value" in row and pd.notna(row["raw_value"]):
                raw_price_val = row["raw_value"]

    if raw_price_val is None and listing_key in raw_by_listing_key:
        raw_rec = raw_by_listing_key[listing_key]
        if isinstance(raw_rec, dict):
            dicts_to_check = [raw_rec]
            for sub_k in ("product", "stats", "item"):
                sub_d = raw_rec.get(sub_k)
                if isinstance(sub_d, dict):
                    dicts_to_check.append(sub_d)

            for d in dicts_to_check:
                for k, v in d.items():
                    k_lower = str(k).lower()
                    if "price" in k_lower and v is not None and not pd.isna(v):
                        raw_price_val = v
                        if price_source is None:
                            price_source = "raw_jsonl"
                        break
                if raw_price_val is not None:
                    break

    return raw_price_val, price_source


def detect_extreme_prices(
    dataset: ReadinessDataset,
    *,
    config: MLReadinessConfig,
) -> tuple[ExtremePriceObservation, ...]:
    products_df = dataset.products
    if products_df.empty or "price" not in products_df.columns:
        return ()

    valid_prices = pd.to_numeric(products_df["price"], errors="coerce").dropna()
    if valid_prices.empty:
        return ()

    q_lower = float(valid_prices.quantile(config.extremes.price_lower_quantile))
    q_upper = float(valid_prices.quantile(config.extremes.price_upper_quantile))
    q25 = float(valid_prices.quantile(0.25))
    q75 = float(valid_prices.quantile(0.75))
    iqr = q75 - q25
    iqr_lower = q25 - config.extremes.iqr_multiplier * iqr
    iqr_upper = q75 + config.extremes.iqr_multiplier * iqr

    median_val = float(valid_prices.median())
    mad_val = float((valid_prices - median_val).abs().median())

    observations: list[ExtremePriceObservation] = []

    for _, row in products_df.iterrows():
        price_raw = row["price"]
        if pd.isna(price_raw):
            continue
        try:
            price_val = float(price_raw)
        except (ValueError, TypeError):
            continue

        lower_quantile_flag = bool(price_val < q_lower)
        upper_quantile_flag = bool(price_val > q_upper)
        iqr_flag = bool(price_val < iqr_lower or price_val > iqr_upper)

        if mad_val > 0.0:
            robust_z_score = float(0.6745 * (price_val - median_val) / mad_val)
            robust_z_flag = bool(abs(robust_z_score) >= config.extremes.robust_z_threshold)
        else:
            robust_z_score = None
            robust_z_flag = False

        triggers: list[str] = []
        if lower_quantile_flag:
            triggers.append("lower_quantile")
        if upper_quantile_flag:
            triggers.append("upper_quantile")
        if iqr_flag:
            triggers.append("iqr")
        if robust_z_flag:
            triggers.append("robust_z")

        if not triggers:
            continue

        listing_key = str(row["listing_key"]) if ("listing_key" in row and pd.notna(row["listing_key"])) else ""
        product_name = str(row["product_name"]) if ("product_name" in row and pd.notna(row["product_name"])) else None
        product_url = str(row["product_url"]) if ("product_url" in row and pd.notna(row["product_url"])) else None
        breadcrumb = str(row["breadcrumb"]) if ("breadcrumb" in row and pd.notna(row["breadcrumb"])) else None
        shop_name = str(row["shop_name"]) if ("shop_name" in row and pd.notna(row["shop_name"])) else None

        raw_price_val, price_source = _extract_raw_price_info(
            listing_key, dataset.provenance, dataset.raw_by_listing_key
        )

        obs = ExtremePriceObservation(
            listing_key=listing_key,
            product_name=product_name,
            product_url=product_url,
            price=price_val,
            breadcrumb=breadcrumb,
            shop_name=shop_name,
            lower_quantile_flag=lower_quantile_flag,
            upper_quantile_flag=upper_quantile_flag,
            iqr_flag=iqr_flag,
            robust_z_flag=robust_z_flag,
            robust_z_score=robust_z_score,
            trigger_names=tuple(triggers),
            raw_price_value=raw_price_val,
            price_source=price_source,
            review_status="UNREVIEWED",
            review_note="",
        )
        observations.append(obs)

    observations.sort(
        key=lambda o: (
            -len(o.trigger_names),
            -abs(o.robust_z_score) if o.robust_z_score is not None else 1.0,
            o.price,
            o.listing_key,
        )
    )

    return tuple(observations)
