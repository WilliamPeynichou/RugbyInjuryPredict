"""Écrit le schéma OpenAPI de l'API publique dans web/openapi.json (F26, `make openapi`)."""

import json
from pathlib import Path

from rugby_risk.api.main import create_app

TARGET = Path("web/openapi.json")


def main() -> None:
    schema = create_app().openapi()
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OpenAPI écrit : {TARGET}")


if __name__ == "__main__":
    main()
