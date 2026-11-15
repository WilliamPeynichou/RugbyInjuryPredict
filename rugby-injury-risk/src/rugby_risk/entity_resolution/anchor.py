"""Deterministic anchor: LNR player IDs, allrugby attached on shared matches."""

import polars as pl

from rugby_risk.reference import team_canonical


def anchor_pairs(appearances: pl.DataFrame) -> pl.DataFrame:
    """Pairs (lnr key, allrugby key) present in the same match, same club, same shirt number.

    One row per pair. Appearances carry: key, match_key, match_date, team (raw) and
    shirt_number.
    """
    if appearances.is_empty():
        return pl.DataFrame(schema={"key_l": pl.String, "key_r": pl.String, "anchor": pl.Boolean})
    both = appearances.filter(pl.col("source").is_in(["lnr", "allrugby"])).with_columns(
        pl.struct(["team", "source"])
        .map_elements(
            lambda t: team_canonical(t["team"], t["source"]) or t["team"], return_dtype=pl.String
        )
        .alias("team")
    )
    lnr = both.filter(pl.col("source") == "lnr").select(
        pl.col("key").alias("key_l"), "match_key", "team", "shirt_number"
    )
    allrugby = both.filter(pl.col("source") == "allrugby").select(
        pl.col("key").alias("key_r"), "match_key", "team", "shirt_number"
    )
    pairs = lnr.join(allrugby, on=["match_key", "team", "shirt_number"], how="inner")
    return pairs.select("key_l", "key_r", pl.lit(True).alias("anchor")).unique()
