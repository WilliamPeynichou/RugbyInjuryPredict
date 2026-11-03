import argparse
from collections.abc import Sequence

from rugby_risk.http.store import RawStore


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rugby-risk")
    sub = parser.add_subparsers(dest="group", required=True).add_parser("raw")
    ls = sub.add_subparsers(dest="cmd", required=True).add_parser("ls")
    ls.add_argument("--source")
    args = parser.parse_args(argv)
    for row in RawStore().iter_manifest(args.source):
        stamp = f"{row.fetched_at:%Y-%m-%dT%H:%M:%SZ}"
        print(f"{stamp} {row.status} {row.sha256[:12]} {row.source} {row.url_canonical}")
    return 0
