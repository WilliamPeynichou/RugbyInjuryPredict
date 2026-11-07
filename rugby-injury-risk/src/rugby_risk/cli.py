import argparse
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path

from rugby_risk.analysis.sequences import write_report as write_sequences_report
from rugby_risk.entity_resolution.review import decide, read_review_queue
from rugby_risk.http.store import RawStore
from rugby_risk.injuries import evaluate
from rugby_risk.injuries.absence_report import write_report as write_absences_report
from rugby_risk.injuries.annotation import (
    ANNOTATIONS_PATH,
    draw_sample,
    record_decision,
)
from rugby_risk.injuries.exit_report import write_report
from rugby_risk.warehouse import connect


def _train(model_name: str, config_path: Path) -> int:
    """F18: entraînement via le runner (splits par saison, MLflow, rapport)."""
    import polars as pl  # noqa: PLC0415
    import yaml  # noqa: PLC0415 - import paresseux : évite sklearn/mlflow au démarrage

    from rugby_risk.modeling.null import registry  # noqa: PLC0415
    from rugby_risk.modeling.runner import (  # noqa: PLC0415
        ExperimentConfig,
        run_experiment,
    )

    factories = registry()
    if model_name not in factories:
        raise SystemExit(f"Modèle inconnu: {model_name} (disponibles: {sorted(factories)})")
    overrides = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    config = ExperimentConfig(**overrides)
    export_path = Path("data/ml/ml_player_match.parquet")
    if not export_path.exists():
        raise SystemExit(
            f"Export introuvable: {export_path} — lancer d'abord le pipeline"
            " (scripts/run_pipeline.sh) pour matérialiser l'asset ml_table."
        )
    df = pl.read_parquet(export_path)
    result = run_experiment(factories[model_name], df, config)
    print(f"Rapport : {result.report_path}")
    print(f"Log-loss pooled: {result.aggregated.log_loss:.4f}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:  # noqa: PLR0911, PLR0912, PLR0915
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
    report = sub.add_parser("report", help="rapports agrégés (sans donnée nominative)")
    report_sub = report.add_subparsers(dest="cmd", required=True)
    report_sub.add_parser("sequences", help="reports/descriptive_sequences.md (F11)")
    report_sub.add_parser("exits", help="reports/exit_calibration.md (F12)")
    report_sub.add_parser("absences", help="reports/absence_reasons.md (F13)")
    report_sub.add_parser(
        "injury-quality", help="reports/injury_label_quality.md (F16, après annotation)"
    )
    train = sub.add_parser("train", help="entraîne un modèle via le cadre F18")
    train.add_argument("model_name", help="nom dans rugby_risk.modeling.null.registry()")
    train.add_argument("--config", default="configs/experiments/_example.yaml")
    annotate = sub.add_parser(
        "annotate", help="échantillon d'annotation humaine des épisodes (F16)"
    )
    annotate_sub = annotate.add_subparsers(dest="cmd", required=True)
    sample_parser = annotate_sub.add_parser("sample", help="tire et affiche l'échantillon")
    sample_parser.add_argument("--n", type=int, default=400)
    sample_parser.add_argument("--seed", type=int, default=42)
    decide_parser = annotate_sub.add_parser("decide", help="enregistre une décision humaine")
    decide_parser.add_argument("key")
    decide_parser.add_argument("decision", choices=["injury", "not_injury", "unsure"])
    decide_parser.add_argument("--kind", choices=["episode", "non_episode"], default="episode")
    decide_parser.add_argument("--confidence", type=float, default=0.0)
    args = parser.parse_args(argv)
    if args.group == "report":
        with closing(connect()) as con:
            if args.cmd == "exits":
                out, writer = Path("reports/exit_calibration.md"), write_report
            elif args.cmd == "absences":
                out, writer = Path("reports/absence_reasons.md"), write_absences_report
            elif args.cmd == "injury-quality":
                metrics = evaluate.compute_metrics(evaluate.load_annotations(ANNOTATIONS_PATH))
                out = Path("reports/injury_label_quality.md")
                out.write_text(
                    evaluate.quality_report_markdown(
                        evaluate.load_annotations(ANNOTATIONS_PATH), metrics
                    ),
                    encoding="utf-8",
                )
                print(f"Rapport écrit : {out}")
                return 0
            else:
                out, writer = Path("reports/descriptive_sequences.md"), write_sequences_report
            path = writer(con, out)
        print(f"Rapport écrit : {path}")
        return 0
    if args.group == "annotate":
        if args.cmd == "sample":
            with closing(connect()) as con:
                sample = draw_sample(con, n=args.n, seed=args.seed)
            out = Path("data/review/annotation_sample.csv")
            out.parent.mkdir(parents=True, exist_ok=True)
            with out.open("w", encoding="utf-8") as fh:
                fh.write("episode_kind,key,season,band,confidence,summary\n")
                for item in sample:
                    fh.write(
                        f"{item.episode_kind},{item.key},{item.season},"
                        f"{item.band},{item.confidence:.4f},{item.summary}\n"
                    )
            for item in sample[:50]:
                print(f"[{item.episode_kind}] {item.key} {item.summary}")
            print(f"{len(sample)} items -> {out}")
            return 0
        path = record_decision(args.key, args.kind, args.decision, args.confidence)
        print(f"Décision enregistrée dans {path}")
        return 0
    if args.group == "train":
        return _train(args.model_name, Path(args.config))
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
