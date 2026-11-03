import json

import structlog

from rugby_risk.logging import configure_logging


def test_production_log_is_json(capsys):
    configure_logging(production=True)
    structlog.get_logger().info("example", value=1)
    assert json.loads(capsys.readouterr().out)["value"] == 1
