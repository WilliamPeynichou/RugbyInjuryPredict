"""Génère le README racine (page d'accueil GitHub) depuis rugby-injury-risk/README.md."""

from pathlib import Path

PREFIX = "rugby-injury-risk/"
DOCS = (
    "docs/00-vision.md",
    "docs/02-science-priors.md",
    "docs/03-architecture.md",
    "docs/04-data-model.md",
    "docs/06-modeling.md",
    "docs/07-legal-rgpd.md",
    "docs/10-implementation-status.md",
    "features/ROADMAP.md",
    "CLAUDE.md",
)
NOTE = (
    "<!-- Copie racine de rugby-injury-risk/README.md (page d'accueil GitHub). "
    "Source unique : rugby-injury-risk/README.md, régénérer avec `make root-readme`. -->\n\n"
)


def build(text: str) -> str:
    text = text.replace("](docs/img/", f"]({PREFIX}docs/img/")
    for doc in DOCS:
        text = text.replace(f"| `{doc}` |", f"| [`{doc}`]({PREFIX}{doc}) |")
    clone = "git clone <repo> && cd rugby-injury-risk"
    url = (
        "git clone git@github.com:WilliamPeynichou/RugbyInjuryPredict.git\n"
        "cd RugbyInjuryPredict/rugby-injury-risk"
    )
    return NOTE + text.replace(clone, url)


if __name__ == "__main__":
    source = Path(__file__).resolve().parents[1] / "README.md"
    target = source.parents[1] / "README.md"
    target.write_text(build(source.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"écrit : {target}")
