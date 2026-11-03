import pytest

from rugby_risk.http import canonicalize_url

pytestmark = pytest.mark.unit


def test_canonicalize():
    assert (
        canonicalize_url("HTTPS://Demo.test/p?b=2&utm_source=x&a=1#frag", {"c": "3"})
        == "https://demo.test/p?a=1&b=2&c=3"
    )
    assert canonicalize_url("https://demo.test/p") == "https://demo.test/p"
