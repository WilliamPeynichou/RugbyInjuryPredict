"""Splink (DuckDB backend) Fellegi-Sunter scoring of candidate player pairs.

shortcut: m/u probabilities fixed by hand (no EM training): fixtures are too small to train
on. Upgrade: estimate_u_using_random_sampling + EM on the first real run, then freeze the
trained settings JSON here.
"""

import logging

import polars as pl
import splink.comparison_level_library as cll
import splink.comparison_library as cl
from splink import DuckDBAPI, Linker, SettingsCreator, block_on

AUTO_LINK = 0.95
REVIEW = 0.6
COLUMNS = ["key", "name_norm", "name_block", "birth_date", "birth_year", "nationality", "teams"]


def _settings() -> SettingsCreator:
    name = cl.CustomComparison(
        output_column_name="name_norm",
        comparison_levels=[
            cll.NullLevel("name_norm"),
            cll.ExactMatchLevel("name_norm").configure(m_probability=0.80, u_probability=0.0002),
            cll.JaroWinklerLevel("name_norm", 0.95).configure(
                m_probability=0.10, u_probability=0.001
            ),
            cll.LevenshteinLevel("name_norm", 2).configure(m_probability=0.05, u_probability=0.002),
            cll.JaroWinklerLevel("name_norm", 0.88).configure(
                m_probability=0.04, u_probability=0.02
            ),
            cll.ElseLevel().configure(m_probability=0.01, u_probability=0.9768),
        ],
    )
    return SettingsCreator(
        link_type="dedupe_only",
        unique_id_column_name="key",
        probability_two_random_records_match=0.001,
        comparisons=[
            name,
            cl.ExactMatch("birth_date").configure(
                m_probabilities=[0.95, 0.05], u_probabilities=[0.0003, 0.9997]
            ),
            cl.ExactMatch("nationality").configure(
                m_probabilities=[0.9, 0.1], u_probabilities=[0.15, 0.85]
            ),
            cl.ArrayIntersectAtSizes("teams", [1]).configure(
                m_probabilities=[0.8, 0.2], u_probabilities=[0.02, 0.98]
            ),
        ],
        blocking_rules_to_generate_predictions=[
            block_on("name_block", "birth_year"),
            block_on("teams", arrays_to_explode=["teams"]),
            block_on("name_norm"),  # internationaux : ni club ni date de naissance
        ],
        retain_intermediate_calculation_columns=False,
    )


def score_pairs(records: pl.DataFrame, threshold: float = REVIEW) -> pl.DataFrame:
    """Candidate pairs (key_l, key_r, match_probability) with probability >= threshold."""
    empty = pl.DataFrame(
        schema={"key_l": pl.String, "key_r": pl.String, "match_probability": pl.Float64}
    )
    if records.height < 2:  # noqa: PLR2004
        return empty
    db_api = DuckDBAPI()
    table = db_api.register(records.select(COLUMNS).to_arrow())
    linker = Linker(table, _settings(), log_level=logging.WARNING)
    rows = linker.inference.predict(threshold_match_probability=threshold).as_record_list()
    if not rows:
        return empty
    return pl.DataFrame(
        [
            {"key_l": r["key_l"], "key_r": r["key_r"], "match_probability": r["match_probability"]}
            for r in rows
        ],
        schema=empty.schema,
    )
