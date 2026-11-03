"""dbt-duckdb plugin: registers the same `player_key` as the Python code, so keys cannot diverge."""

import duckdb
from dbt.adapters.duckdb.plugins import BasePlugin
from duckdb.sqltypes import BIGINT, VARCHAR

from rugby_risk.privacy import player_key


def _udf(player_id: int) -> str:
    return player_key(player_id)  # one-arg wrapper: DuckDB counts the optional `salt` parameter


class Plugin(BasePlugin):
    def configure_connection(self, conn: duckdb.DuckDBPyConnection) -> None:
        conn.create_function("player_key", _udf, [BIGINT], VARCHAR)
