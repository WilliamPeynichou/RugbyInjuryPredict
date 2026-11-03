import pytest

from rugby_risk.parsers.lnr import load_position_aliases
from rugby_risk.reference import positions

pytestmark = pytest.mark.unit


def test_all_aliases_point_to_valid_codes():
    valid = set(positions()["position_code"].to_list())
    aliases = load_position_aliases()
    assert aliases
    assert set(aliases.values()) <= valid
    assert all(label and code for label, code in aliases.items())
