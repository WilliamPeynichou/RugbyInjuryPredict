"""Union of entity keys: anchor + Splink pairs, guarded; overrides applied; stable IDs."""

from collections.abc import Iterable

import polars as pl


class _Groups:
    """Union-find over keys, with merge guards."""

    def __init__(self, keys: Iterable[str]) -> None:
        self.parent = {k: k for k in keys}

    def find(self, key: str) -> str:
        root = key
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[key] != root:
            self.parent[key], key = root, self.parent[key]
        return root

    def union(self, left: str, right: str) -> bool:
        rl, rr = self.find(left), self.find(right)
        if rl == rr:
            return False
        self.parent[max(rl, rr)] = min(rl, rr)
        return True


def _assign_ids(
    members: dict[str, list[str]],
    previous_ids: dict[str, int],
    anchored_keys: set[str],
    anchor: pl.DataFrame,
) -> tuple[dict[str, int], dict[str, str]]:
    """One player_id per group: smallest reusable previous id, else a new sequence id."""
    {(p["key_l"], p["key_r"]) for p in anchor.to_dicts()}
    used: set[int] = set()
    next_id = max(previous_ids.values(), default=0) + 1
    assigned: dict[str, int] = {}
    method: dict[str, str] = {}
    for root in sorted(members):
        candidates = sorted(previous_ids[k] for k in members[root] if k in previous_ids)
        player_id = next((c for c in candidates if c not in used), None)
        if player_id is None:
            while next_id in used:
                next_id += 1
            player_id = next_id
            next_id += 1
        used.add(player_id)
        for key in members[root]:
            assigned[key] = player_id
            method[key] = "anchor_lnr" if key in anchored_keys else "splink"
    return assigned, method


def resolve_entities(  # noqa: PLR0912, PLR0913, PLR0915, PLR0917 - pipeline wiring
    records: pl.DataFrame,
    anchor: pl.DataFrame,
    scored: pl.DataFrame,
    apps: pl.DataFrame,
    previous: pl.DataFrame | None,
    overrides: pl.DataFrame,
    *,
    auto_link: float = 0.95,
    review: float = 0.6,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Return (xref, review queue).

    xref: key, source, source_player_id, player_id, match_confidence, method.
    Review queue: key_l, key_r, match_probability for pairs in [review, auto_link[ and for
    blocked merges (probability set to NULL for those).
    """
    keys = records["key"].to_list()
    groups = _Groups(keys)
    by_key = {r["key"]: r for r in records.to_dicts()}

    matches_by_key: dict[str, dict[str, set[str]]] = {}
    for row in apps.to_dicts():
        dates = matches_by_key.setdefault(row["key"], {})
        dates.setdefault(row["match_date"], set()).add(row["match_key"])

    def mergeable(left: str, right: str) -> bool:
        # jamais deux fiches LNR dans un même groupe (identité LNR = ancre)
        if by_key[left]["source"] == "lnr" and by_key[right]["source"] == "lnr":
            return False
        # un joueur ne joue pas deux matchs différents le même jour (invariant 1) :
        # une date partagée doit donc désigner le même match_key.
        left_dates = matches_by_key.get(left, {})
        for day, keys in matches_by_key.get(right, {}).items():
            if day in left_dates and left_dates[day] != keys:
                return False
        return True

    for pair in anchor.to_dicts():
        if mergeable(pair["key_l"], pair["key_r"]):
            groups.union(pair["key_l"], pair["key_r"])

    review_rows: list[dict[str, object]] = []
    for pair in scored.sort("match_probability", descending=True).to_dicts():
        left, right, probability = pair["key_l"], pair["key_r"], float(pair["match_probability"])
        if probability >= auto_link:
            if mergeable(left, right):
                groups.union(left, right)
            else:
                review_rows.append({"key_l": left, "key_r": right, "match_probability": None})
        else:
            review_rows.append({"key_l": left, "key_r": right, "match_probability": probability})

    forced: dict[str, str] = {}
    rejected: set[str] = set()
    for row in overrides.to_dicts():
        if str(row["player_id"]) == "REJECT":
            rejected.add(row["key"])
        else:
            forced[row["key"]] = str(row["player_id"])

    members: dict[str, list[str]] = {}
    for key in keys:
        if key not in forced:
            members.setdefault(groups.find(key), []).append(key)

    previous_ids: dict[str, int] = {}
    if previous is not None and not previous.is_empty():
        previous_ids = {str(r["key"]): int(r["player_id"]) for r in previous.to_dicts()}

    anchored_keys = {k for p in anchor.to_dicts() for k in (p["key_l"], p["key_r"])}
    assigned, method = _assign_ids(members, previous_ids, anchored_keys, anchor)
    used_ids = set(assigned.values())
    next_new = max(used_ids, default=0) + 1
    for key, pid in forced.items():
        if pid == "NEW":
            while next_new in used_ids:
                next_new += 1
            assigned[key] = next_new
            used_ids.add(next_new)
            next_new += 1
        else:
            assigned[key] = int(pid)
            used_ids.add(int(pid))
        method[key] = "manual_override"
    xref_rows = [
        {
            "key": key,
            "source": by_key[key]["source"],
            "source_player_id": by_key[key]["source_player_id"],
            "player_id": assigned[key],
            "match_confidence": None,
            "method": method[key],
        }
        for key in keys
        if key in assigned and key not in rejected
    ]
    xref_schema = {
        "key": pl.String,
        "source": pl.String,
        "source_player_id": pl.String,
        "player_id": pl.Int64,
        "match_confidence": pl.Float64,
        "method": pl.String,
    }
    xref = pl.DataFrame(xref_rows, schema=xref_schema)
    queue_schema = {"key_l": pl.String, "key_r": pl.String, "match_probability": pl.Float64}
    queue = (
        pl.DataFrame(review_rows, schema=queue_schema)
        if review_rows
        else pl.DataFrame(schema=queue_schema)
    )
    return xref, queue
