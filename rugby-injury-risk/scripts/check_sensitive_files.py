import sys
from pathlib import PurePosixPath


def is_sensitive(filename: str) -> bool:
    path = PurePosixPath(filename)
    parts = path.parts
    return (
        any(parts[i : i + 2] in (("data", "raw"), ("data", "staging")) for i in range(len(parts)))
        or path.name.endswith(".duckdb")
        or path.name == ".env"
        or "mlruns" in parts
    )


if __name__ == "__main__":
    rejected = [name for name in sys.argv[1:] if is_sensitive(name)]
    if rejected:
        sys.stderr.write("Fichiers sensibles interdits : " + ", ".join(rejected) + "\n")
        sys.exit(1)
