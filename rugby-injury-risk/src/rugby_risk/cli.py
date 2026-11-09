import argparse
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path
from typing import Any

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


def _experiment_inputs(config_path: Path) -> tuple[Any, Any, Any]:
    """Model registry, ExperimentConfig and the ML export (F18 entry point)."""
    import polars as pl  # noqa: PLC0415
    import yaml  # noqa: PLC0415 - import paresseux : évite sklearn/mlflow au démarrage

    from rugby_risk.modeling.null import registry  # noqa: PLC0415
    from rugby_risk.modeling.runner import ExperimentConfig  # noqa: PLC0415

    overrides = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    export_path = Path("data/ml/ml_player_match.parquet")
    if not export_path.exists():
        raise SystemExit(
            f"Export introuvable: {export_path} — lancer d'abord le pipeline"
            " (scripts/run_pipeline.sh) pour matérialiser l'asset ml_table."
        )
    return registry(), ExperimentConfig(**overrides), pl.read_parquet(export_path)


def _train(model_name: str, config_path: Path, *, fast: bool = False) -> int:
    """F18: entraînement via le runner (splits par saison, MLflow, rapport)."""
    from rugby_risk.modeling.runner import run_experiment  # noqa: PLC0415

    factories, config, df = _experiment_inputs(config_path)
    name = f"{model_name}_fast" if fast else model_name
    if name not in factories:
        raise SystemExit(f"Modèle inconnu: {name} (disponibles: {sorted(factories)})")
    result = run_experiment(factories[name], df, config)
    print(f"Rapport : {result.report_path}")
    print(f"Log-loss pooled: {result.aggregated.log_loss:.4f}")
    return 0


def _review(config_path: Path, *, fast: bool, sensitivities: bool) -> int:
    """F22: M2 + M0/M1/M1w + sensibilités -> reports/model_review_<run_id>.md."""
    from rugby_risk.modeling.review import run_review, write_review  # noqa: PLC0415

    if not sensitivities:
        raise SystemExit("La revue de modèle exige les sensibilités (docs/06 §3.3).")
    factories, config, df = _experiment_inputs(config_path)
    main = "m2_hierarchical_fast" if fast else "m2_hierarchical"
    if fast:  # sensibilités dans le même mode que le modèle principal
        factories = {**factories, f"{main}_noipw": factories["m2_hierarchical_noipw_fast"]}
    review = run_review(df, config, factories, main=main)
    print(f"Revue : {write_review(review)}")
    return 0


def _fit_final(model_name: str, config_path: Path) -> int:
    """F30: refit M2 on every validated season, persist it locally (data/models/)."""
    from rugby_risk.modeling.artifact import save_hierarchical  # noqa: PLC0415
    from rugby_risk.modeling.hierarchical import HierarchicalHazardModel  # noqa: PLC0415
    from rugby_risk.modeling.runner import fit_final  # noqa: PLC0415

    factories, config, df = _experiment_inputs(config_path)
    if model_name not in factories:
        raise SystemExit(f"Modèle inconnu: {model_name} (disponibles: {sorted(factories)})")
    final = fit_final(factories[model_name], df, config)
    if not isinstance(final.model, HierarchicalHazardModel):
        raise SystemExit("fit-final ne persiste que les modèles M2 (hiérarchiques)")
    path = save_hierarchical(
        final.model,
        final.train,
        seasons=final.seasons,
        dataset_version=final.dataset_version,
        git_sha=final.git_sha,
    )
    print(f"Artefact : {path} (MCMC {final.model.status}, saisons {', '.join(final.seasons)})")
    return 0 if final.model.status == "ok" else 1


def _profile(args: Any) -> int:
    """F30: risk per chained match for a typed load profile (by position, never by name)."""
    from datetime import UTC, datetime  # noqa: PLC0415

    from rugby_risk.modeling.artifact import (  # noqa: PLC0415
        is_promoted,
        latest_artifact,
        load_hierarchical,
    )
    from rugby_risk.modeling.profile import (  # noqa: PLC0415
        PositionProfile,
        profile_markdown,
        simulate,
    )

    directory = Path(args.model_dir) if args.model_dir else latest_artifact()
    model, meta = load_hierarchical(directory)
    profile = PositionProfile(
        position_code=args.position.upper(),
        minutes_per_match=args.minutes,
        apps_20min_365d=args.apps_365d,
        min_28d=args.min_28d,
        intl_window=args.intl_window,
        days_since_last_match=args.rest_days,
        start_consecutive=args.start,
        horizon=args.horizon,
    )
    md = profile_markdown(simulate(model, profile), model, meta, promoted=is_promoted(directory))
    out = Path("reports/profiles")
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = out / f"profile-{profile.position_code}-{stamp}.md"
    path.write_text(md, encoding="utf-8")
    print(md)
    print(f"Rapport : {path}")
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
    train.add_argument("--fast", action="store_true", help="variante <modèle>_fast (itération)")
    review_model = sub.add_parser("review-model", help="revue M2 (F22) : model_review_<id>.md")
    review_model.add_argument("--config", default="configs/experiments/m2_hierarchical.yaml")
    review_model.add_argument("--fast", action="store_true", help="M2 --fast (exploration)")
    review_model.add_argument("--no-sensitivities", action="store_true")
    final = sub.add_parser(
        "fit-final", help="ajuste M2 sur toutes les saisons validées -> data/models/ (F30)"
    )
    final.add_argument("model_name", nargs="?", default="m2_hierarchical")
    final.add_argument("--config", default="configs/experiments/m2_hierarchical.yaml")
    prof = sub.add_parser(
        "profile", help="risque par match enchaîné pour un profil de charge par poste (F30)"
    )
    prof.add_argument("--position", required=True, help="code poste, ex. FLY_HALF")
    prof.add_argument("--minutes", type=float, default=80.0, help="minutes par match")
    prof.add_argument("--apps-365d", type=float, help="matchs >= 20 min sur 365 j")
    prof.add_argument("--min-28d", type=float, help="minutes jouées sur 28 j")
    prof.add_argument("--intl-window", action="store_true")
    prof.add_argument("--rest-days", type=float, default=7.0)
    prof.add_argument("--start", type=int, default=0, help="matchs consécutifs déjà joués")
    prof.add_argument("--horizon", type=int, default=6)
    prof.add_argument("--model-dir", help="artefact (défaut : le plus récent de data/models)")
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
        return _train(args.model_name, Path(args.config), fast=args.fast)
    if args.group == "review-model":
        return _review(Path(args.config), fast=args.fast, sensitivities=not args.no_sensitivities)
    if args.group == "fit-final":
        return _fit_final(args.model_name, Path(args.config))
    if args.group == "profile":
        return _profile(args)
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
