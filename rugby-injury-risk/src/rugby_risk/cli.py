import argparse
from collections.abc import Sequence

from rugby_risk.entity_resolution.review import decide, read_review_queue
from rugby_risk.http.store import RawStore


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rugby-risk")
    sub = parser.add_subparsers(dest="group", required=True)
    raw = sub.add_parser("raw")
    ls = raw.add_subparsers(dest="cmd", required=True).add_parser("ls")
    ls.add_argument("--source")
    er = sub.add_parser("er", help="revue manuelle des liens d'entités incertains")
    er_sub = er.add_subparsers(dest="cmd", required=True)
    er_sub.add_parser("review", help="affiche la file de revue (data/review/er_queue.csv)")
    decide_parser = er_sub.add_parser("decide", help="enregistre une décision humaine")
    decide_parser.add_argument("key", help="identifiant source:source_player_id")
    decide_parser.add_argument("player_id", help="player_id existant, NEW ou REJECT")
    args = parser.parse_args(argv)
    if args.group == "er":
        if args.cmd == "review":
            queue = read_review_queue()
            if queue.is_empty():
                print("File de revue vide.")
            for pair in queue.to_dicts():
                print(f"{pair['key_l']} <-> {pair['key_r']}  p={pair['match_probability']}")
        else:
            path = decide(args.key, args.player_id)
            print(f"Décision enregistrée dans {path}")
        return 0
    for entry in RawStore().iter_manifest(args.source):
        stamp = f"{entry.fetched_at:%Y-%m-%dT%H:%M:%SZ}"
        print(f"{stamp} {entry.status} {entry.sha256[:12]} {entry.source} {entry.url_canonical}")
    return 0
