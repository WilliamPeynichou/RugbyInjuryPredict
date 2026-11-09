# 10 — Journal d'implémentation (état des lieux)

État au 2026-11-05, features F00 à F15 livrées (F14 héritée, fiche à reprendre).

Ce document est la vue d'ensemble pour reprendre le développement :
1. ce qui est fait ;
2. les soucis recensés ;
3. ce qui reste à faire ;
4. les règles à appliquer.

Les sources de vérité détaillées restent :
- `features/ROADMAP.md` pour les statuts ;
- le **Journal** de chaque fiche `features/Fxx-*.md` pour les décisions et les écarts ;
- `docs/00` à `docs/09` pour les règles.

## 1. Vue d'ensemble

| Phase | Features | Statut |
|---|---|---|
| 0 — Socle | F00 bootstrap, F01 registre des sources, F02 données de référence | ✅ fait |
| 1 — Collecte et entrepôt | F03 HTTP et lac brut, F04 DuckDB/dbt, F05 allrugby, F06 LNR | ✅ fait |
| 2 — Internationaux, coupes, entités | F07 → F11 | ✅ fait |
| 3 — Labellisation des blessures | F12, F13, F15, F16 ✅ ; F14 (fiche à reprendre, T9) | ✅ fait (sauf annotation humaine) |
| 4 — Table d'apprentissage et baselines | F17, F18, F19, F20 ✅ | ✅ fait |
| 5 — Modèle de production | F21, F22 ✅ | ✅ fait |
| 6 — Challenger et gravité | F23, F24 | ⬜ à faire |
| 7 — Produit | F25 → F27 | ⬜ à faire |
| 8 — Exploitation | F28, F29 | ⬜ à faire |

Le dernier `make check` local est vert (F22) : ruff, format, mypy strict (106 fichiers) et
pytest 344 tests, couverture 88,95 % ; les tests `slow` (fit MCMC de récupération
d'effets, ~2 min) passent via `pytest -m slow`.

Git :
- une branche `feat/Fxx-*` par feature, avec des commits Conventional Commits ;
- les branches sont **empilées** : chacune part de la précédente, et
  `feat/F15-llm-injury-extraction` contient tout l'historique ;
- rien n'est encore fusionné dans une branche `main`.

## 2. Ce qui est fait

| Feature | Commit | Livré |
|---|---|---|
| F00 | `d3d29b8` | Dépôt `uv` (Python 3.12). `make check` exige une couverture ≥ 80 %. Hook pre-commit (secrets, gros fichiers). Workflow CI `.github/workflows/rugby-injury-risk.yml`. Les tests verrouillent `.gitignore` et refusent `.env`, `data/raw`, `data/staging`, `*.duckdb` et `mlruns/`. |
| F01 | `9d36a88` | `config/sources.yaml` déclare 9 sources ; le garde-fou `assert_authorized` est relu à chaque appel, sans cache. `config/seasons.yaml` couvre 2013-14 → 2026-27 (1er juillet–30 juin, sans chevauchement, saisons COVID marquées). |
| F02 | `9793b01` | `data/reference/` : 9 postes, 6 groupes, 2 unités, compétitions, 24 stades, surfaces 2025-26 (page LNR APPE), fenêtres de tests 2013–2027, régimes de protection FFR/LNR. Chargeurs Polars et Pandera. |
| F03 | `ba513e8` | Client HTTP `PoliteClient` : refus des sources non autorisées et des hôtes non déclarés, débit limité par hôte, robots.txt en cache 24 h, nouvelles tentatives sur 429/5xx avec `Retry-After`, en-têtes ETag/Last-Modified, mode `offline`. Lac brut `RawStore` en ajout seul (zstd, écriture atomique, manifeste Parquet). CLI `rugby-risk raw ls`. |
| F04 | `17f5f9d` | Projet `dbt/` (dimensions de référence, staging lisant le Parquet). `warehouse.py` : `connect`, `write_staging`, `upsert` idempotent, `staging_frame`. Contrats `staging_schemas.py`. `privacy.py` (HMAC-SHA256), exposé à dbt comme fonction `player_key`. |
| F05 | `bf1544d` | allrugby : URLs, découverte des pages en ligne, parseurs match (minutes, cartons, mise en quarantaine) et joueur. Coup d'envoi Europe/Paris, heure imputée à 15:00. Assets Dagster partitionnés par saison, recalculés hors ligne depuis le lac brut. |
| F06 | `830d4ad` | LNR activée par décision humaine. Parseur de compositions (identifiants LNR, postes normalisés via `position_aliases.csv`, minutes `NULL`). Partitions saison × journée. Rapport `lnr_vs_allrugby` → `data/staging/_reports/lineup_diff/`. |
| F07 | `1c476eb` | World Rugby : minutes reconstruites (`Sub On/Off`, `IR`/`HIAO` en bascule, rouge = sortie définitive). ESPN : compositions, minutes `NULL`. Correspondance des compétitions via `competition_aliases.csv`, avec repli selon le mois. Féminin, rugby à 7 et jeunes exclus. Assets `intl_staging_worldrugby` et `intl_staging_espn`, rapport `intl_minutes_check`. |
| F08 | `4671523` | Coupes d'Europe via ESPN (`parse_europe` : Champions/Challenge Cup avec au moins un club français) → `staging/match/source=espn_europe`. Page calendrier = `scoreboard` ESPN. `team_aliases.csv` (+ `country`) et `venue_aliases.csv` (→ `venue_id`). Calendrier unifié `staging/fixture_calendar` (une ligne par clé naturelle, priorité LNR > allrugby > World Rugby > ESPN > API-Sports, heure imputée toujours battue), rapport `_reports/calendar_conflicts` (> 2 h). |
| F09 | `81f409f` | Résolution d'entités joueurs : ancre lnr↔allrugby (même match, club, maillot), Splink 5 (DuckDB, m/u fixés, auto ≥ 0,95, revue ≥ 0,6), union-find avec gardes, overrides humains (`er_overrides.csv`), IDs stables. Tables `player_source_xref`, `er_dim_player`, 3 asset checks, CLI `rugby-risk er review/decide`. |
| F10 | `3d89672` | Marts dbt `dim_team`, `fact_match`, `fact_appearance`, `fact_squad_membership`, `fact_eligibility`, `match_minutes_check`, `dim_season.quality_flag`. Ids stables (md5 de la clé naturelle). Asset `participation_marts` (dbtRunner, sans dagster-dbt) + check `top14_minutes_quality` (`ERROR` < 98 %). Rapport `reports/coverage.md`. |
| F11 | `2470a0c` | Macro dbt `consecutive_run_id` (seule implémentation des séquences, réutilisée en F17). Modèle `analysis_player_sequences` (séquences par joueur et saison, raison de fin). `analysis/sequences.py` (médiane, P90, max, charge, rotations courtes, k ≥ 10) et figures matplotlib. CLI `rugby-risk report sequences` → `reports/descriptive_sequences.md`. |
| F12 | (voir `feat/F12-signal-exits`) | Seuils dans `config/injury_rules.yaml` (Pydantic → vars dbt). Modèle `int_injury_signal__exit` (force ∈ [0,1], bloc × 0,3, absent-au-match-suivant + 0,2 ; info postérieure, cible uniquement). `off_reason_derived` (sources non écrasées). Rapport `reports/exit_calibration.md`. |
| F13 | `a5bdd9b` | `int_absence_runs` (6 règles ordonnées, censure fin de saison), `int_eligibility__with_reason` (enrichissement sans écrasement), `fact_unavailability` (hors injury_candidate), `int_absence_report`. Seuils dans `config/injury_rules.yaml` (section `absence_signal`). Rapport `reports/absence_reasons.md`. |
| F15 | (ce commit) | Client LLM OpenAI-compatible (httpx, cache disque, retry JSON, tokens loggés) — refuse de s'appeler sans clé validée humainement. Prompt versionné `extract_v1`, schémas Pydantic (`InjuryMention`), conversion durées FR, rattachement joueur (normalize F09 + effectif saison) et match (≤ 7 j), file `data/review/news_player_queue.csv`. Staging `news_doc` + `injury_mention`. Asset `injury_mentions`. Vocabulaires testés contre docs/04. |
| Docs | `0ee73f2` | Première version de ce document. |

### Autorisations de collecte (état réel)

| Source | `authorized` | Note |
|---|---|---|
| lnr | ✅ true | Décision humaine du 2026-11-03, dans le cadre de la fouille de textes et de données (art. L.122-5-3 CPI) : recherche non commerciale, sans redistribution, `min_delay_seconds: 5.0`, robots.txt respecté. **Consigne humaine** : si la LNR bloque (refus, robots, 403/429 persistants), on garde ce qui est déjà collecté, sans contournement. Aucun crawl réel lancé. |
| allrugby, espn, worldrugby, apisports, wikipedia, news | ✅ true | Décision humaine du 2026-11-06, même cadre de fouille de textes et de données. `news` = Rugbyrama RSS seulement. Données de santé : recherche pseudonymisée, modèles expérimentaux non promouvables avant l'avis du juriste. |
| itsrugby, sportradar | ❌ false | Fermées. |

API retenue pour le calendrier (F08) : **API-Sports**. Elle est freemium selon le document de
recherche. Les quotas ne sont pas vérifiés. La clé doit être fournie hors dépôt, via `.env`.

### Décisions et écarts structurants

Les détails sont dans les Journaux des fiches.

1. **Pseudonymisation dbt = même fonction Python** (plugin dbt-duckdb). Il n'y a pas de table
   de correspondance, donc les deux côtés ne peuvent pas diverger.
2. **Pas de `sources.yml` dbt pour le Parquet.** Un glob vide fait échouer DuckDB ; la macro
   `read_staging` renvoie donc une relation vide typée.
3. **Seeds dbt ignorés par git.** `make seeds` les régénère depuis `data/reference/`
   (`NULL` devient une cellule vide).
4. **selectolax avec le moteur lexbor** : le moteur modest est déprécié.
5. **mypy strict assoupli sur `orchestration/`** ; `src/` reste strict.
6. **Polars 2** : les types Pandera sont convertis via `v.type` dans
   `warehouse.staging_frame`.
7. **Assets de staging hors ligne.** Ils sont recalculés depuis le lac brut ; seuls les assets
   `*_raw_*` font des appels réseau.
8. **Clé de partition multi-dimension** : dimensions triées par ordre alphabétique, par exemple
   `J10|2024-2025`.
9. **Heure imputée.** Un coup d'envoi sans heure est fixé à 15:00 Europe/Paris, avec
   `kickoff_time_imputed = true`.
10. **Développement sur fixtures d'abord.** allrugby, LNR, World Rugby et ESPN ont été
    développés sur des fixtures figées ou générées, sans appel réel.
11. **ESPN ne donne pas les minutes** (F07). Le recoupement entre sources compare donc la
    taille des feuilles de match. L'écart de minutes (> 5 %) est contrôlé par rapport à
    15 × 80.
12. **La saison d'un match international est déduite de sa date**, à partir de
    `config/seasons.yaml`. Le lac n'étant pas partitionné, chaque asset filtre sur sa
    partition.
15. **Résolution d'entités** (F09) : ancre déterministe lnr↔allrugby (même match, même club,
    même maillot) + Splink (m/u fixés, sans EM) pour le reste, overrides humains prioritaires.
    Garde d'union : une date partagée doit désigner le même match (invariant 1).
13. **Coupes d'Europe via ESPN**, pas allrugby (F08) : parseur existant, compositions
    incluses. `intl_staging_espn` ne garde que le niveau `international` ; les coupes vont
    sous `source=espn_europe` (colonne `source` = `espn`) pour ne pas s'écraser.
14. **Calendrier** : une heure imputée perd toujours contre une heure observée, quelle que
    soit la source. Les autres colonnes prennent la première valeur non nulle par priorité.
16. **Marts F10** : `read_staging` lit le Parquet avec `hive_partitioning = false` (sinon le
    dossier `source=` écrase la colonne `source`). Minutes inconnues = `NULL` (pas 0) ;
    `played` = `true` pour un titulaire sans minutes, `NULL` pour un remplaçant sans minutes
    (écart documenté dans `docs/04`). Pas de `dagster-dbt` : un asset appelle `dbtRunner`.
19. **LLM F15** : client générique OpenAI-compatible, jamais appelé sans validation humaine
    (clé/fournisseur, docs/07) ; cache disque par (doc_id, prompt_version, model) ; le pipeline
    est testé avec un stub injecté, jamais de réseau. Entrée `news_doc` = contrat F14.
18. **Signaux F12/F13** : seuils dans `config/injury_rules.yaml` (vars dbt) ; les `sources` (fact_appearance, fact_eligibility) ne sont jamais écrasés — les enrichissements (`off_reason_derived`, `absence_reason`) vivent dans des modèles intermédiaires.
17. **Séquences F11** : coupées en fin de saison ; remplaçant sans minutes = non joué (casse
    la séquence). Dépendance `matplotlib` ajoutée (API `Figure`, sans pyplot).

## 3. Soucis recensés (ouverts)

### Données et sources

| # | Souci | Impact | Action prévue |
|---|---|---|---|
| S1 | **allrugby : résolu 2026-11-06** — parseurs réécrits sur markup réel (`allrugby-2`), crawl pilote 2022-23→2024-25 lancé. **LNR : ouvert** — parseur non vérifié sur page réelle. | — | Vérifier le parseur LNR au prochain crawl (1 partition). |
| S2 | **World Rugby : résolu 2026-11-06** — formes réelles vérifiées (cartons `Yellow`/`Red`, quirk id/altId et `teamIndex` peu fiable corrigés). **ESPN : partiel** — ids de ligues vérifiés en direct (Top 14, coupes, 6N, tests) ; parseur JSON non testé sur réponse réelle. | — | Tester le parseur ESPN sur une réponse réelle. |
| S3 | Les identifiants de ligues ESPN hors Top 14 (`180659`, `164205`, `289234`, coupes `271937`, `272073`), les champs de phase (`notes`, `week`) et les noms ESPN des clubs dans `team_aliases.csv` ne sont pas vérifiés. | Mauvaise collecte possible. | À vérifier au premier appel autorisé. |
| S4 | La LNR ne donne pas les minutes. ESPN ne donne ni minutes ni cartons. | Les minutes viennent seulement d'allrugby (club) et de World Rugby (internationaux). Sans allrugby, une saison Top 14 passe `quality_flag = 'low'` et l'asset check F10 échoue (voulu). | Priorité par champ en place (F10). Run réel allrugby nécessaire. |
| S5 | Le Rugby Championship n'a pas de code dans `competitions.csv`. | Il est classé selon le mois (`SUMMER_TESTS`, `AUTUMN_TESTS`, `OTHER_TEST`). | Ajouter un code seulement si `docs/04` évolue (décision humaine). |
| S6 | Fenêtres de tests non sourcées : été 2016, 2019 et 2023, automne 2015, 2016, 2021 et 2022. L'été 2020 n'a pas de fenêtre (COVID, accepté). | `in_test_window` est incomplet sur ces périodes. | Compléter quand la recherche documentaire sera possible ; Wikipédia a renvoyé des 429. |
| S7 | Les 24 stades ont latitude et longitude à `NULL`, et les délocalisations ne sont pas exhaustives. | Pas de feature de déplacement ou de distance. | À compléter avant F17 si `docs/05` l'exige. |
| S8 | Les dates de transition des conventions FFR/LNR (2014, 2017, 2018) sont fixées au 1er juillet par convention. | Approximation du régime de protection. | À confirmer avant l'usage analytique (F11, F13). |
| S9 | Les quotas et la couverture du plan gratuit d'API-Sports ne sont pas vérifiés. Client API-Sports non écrit (F08, pas de clé) ; rang de priorité réservé. | Calendrier sans secours API-Sports. | Lire api-sports.io, puis décision humaine et clé `.env` ; écrire `sources/apisports/` alors. |
| S10 | L'activation de la LNR repose sur l'exception de fouille de textes et de données, sans réponse de la LNR (contact@lnr.fr). | Risque juridique si la LNR fait opposition. | Respecter un opt-out ; en cas de blocage, appliquer la consigne humaine. |
| S11 | **Censure du label en fin de saison** (F20) : `y_injury` vient des absences, qui exigent ≥ 2 matchs d'équipe suivants. 0 blessure sur 677 lignes de phase finale. | Faux négatifs dans le train et le test de tous les modèles. | Corrigé : `with_label_observability` (seuil `absence_signal.min_matches_injury_candidate`) exclut 1 977 lignes jouées du fit et de l'évaluation. Censure résiduelle possible à 2 matchs de suivi (taux 1,1 % vs 1,7 %). |
| S12 | Features constantes ou vides sur le réel 2022-2025 : `age` (100 % NULL, birth_date F09), `surface`, `season_period`, `short_turnaround`, `prior_concussions_365d`. | Termes écartés par `design.py` (listés dans chaque rapport M1). | Compléter birth_date (F09), surfaces (S7), vérifier `short_turnaround` (aucun match à < 6 j ?). |
| S13 | **statsmodels 0.15 ignore `freq_weights`/`var_weights` pour les coefficients d'un GLM Bernoulli** (vérifié contre duplication exacte des lignes, journal F21). | Tout fit pondéré silencieusement non pondéré. | Contourné : forme binomiale groupée `endog = [y·w, (1−y)·w]` (`modeling/hazard.py`). Ne jamais réintroduire `freq_weights` sans re-valider. |
| S14 | `absence_reason` non matérialisé par match dans le mart ml (`fact_eligibility.absence_reason` = `null::varchar` ; le signalement vit en `int_absence_runs`). | Suspensions et devoir international non distinguables par ligne ; le modèle de sélection (F21) utilise des proxies observés (`intl_window`, `protected_list`). | Matérialiser un `absence_reason` par match (joueur × match) si une version future en a besoin ; jusqu'alors IPW = correction sur observables seulement. |
| S15 | **Dataset ml v7** : la colonne `team_id` a été ajoutée à `ml_player_match` (requis par l'effet équipe-saison de F22). Nouveau `dataset_version = 7d004d9a146715b139e501738e58620a` (ancien `e8591d01` invalidé). | Les runs M0/M1/M1w publiés en F20/F21 portaient sur l'ancien dataset et ne sont plus comparables ; ils ont été relancés sur v7 en F22 (journal F22). | Toujours reporter le `dataset_version` dans les comparaisons de modèles. |
| S16 | **Label ML vs incidence attendue** : 1 200 blessures en match détectées (53,9 / 1000 h, dans la bande docs/02), mais seulement 395 au seuil `INJURY_CONF_THRESHOLD = 0,6` (17,7 / 1000 h, soit ~2,4 % par match complet). Les 805 exclues sont surtout des « sorties seules » (0,42 / 0,54 : sortie précoce sans absence ≥ 2 matchs). Le contrôle F16 ne mesurait que la détection. | La cible est des blessures avec arrêt d'au moins 2 matchs, sous-déclarées par construction (doc de recherche § validité de la cible). Le prior M2 (7 %) est au-dessus ; la postérieure s'en écarte (α = −3,73 contre −2,62), donc les courbes M2 réelles (1,2–2,5 %) suivent les données. Ce n'est pas la cause du rejet de M2 (pente de calibration ~0, 1 fold). | Rapport `injury_incidence.md` : 2 sections (détection / label ML) + incidence poolée. Prior M2 inchangé (le recaler sur l'observé serait regarder les données). Toute publication doit dire « blessures avec arrêt ≥ 2 matchs ». |

### Technique et outillage

| # | Souci | Impact | Action prévue |
|---|---|---|---|
| T1 | **Résolu 2026-11-03** : premier push, deux runs GitHub Actions réussis (~1m30 chacun) — le critère CI distante de F00 est clos. Reste le critère « machine distincte » de F00. | — | Tester `make setup` sur une autre machine, puis cocher le critère F00. |
| T2 | **Clos 2026-11-05 (faux positif)** : `--select a,b` matérialise bien chaque asset (vérifié : `STEP_SUCCESS` pour deux assets, Parquet écrits). Seul un avertissement `SupersessionWarning` de la CLI Dagster subsiste. | — | Rien ; migrer vers `dg launch` si la commande disparaît. |
| T3 | **Résolu 2026-11-05** : `.tmp_dagster_home_*/` ajouté à `.gitignore` (et au test `test_gitignore`). | — | — |
| T4 | `make check` dure environ 2 min 15. Dans l'outil shell de l'agent, une session de plus de 2 min est tuée (SIGHUP, `Error 129`) en plein pytest. | Faux échec. | Lancer `make check` détaché, par exemple via un sous-processus avec `start_new_session`, et lire `/tmp/mk.log`. |
| T5 | `allrugby_staging_matches` et `allrugby_staging_appearances` refont la même analyse des pages. | Double coût CPU (négligeable sur fixtures). | Fusionner en un multi-asset si le volume réel le justifie. |
| T6 | Les assets internationaux parcourent tout le manifeste pour chaque saison. | Coût linéaire en taille du lac. | Filtrer par date dans le manifeste si le volume réel le justifie. |
| T7 | La ROADMAP n'avait pas été mise à jour pour F03, F05 et F06. | Corrigé dans F07. | Mettre à jour la ROADMAP dans le commit de chaque feature. |
| T9 | La fiche F14 est `done` en ROADMAP mais cases/Journal vides (code de collecte presse hérité F03, jamais relu feature par feature). | État réel flou. | Reprendre la fiche F14 (cocher, journal) ou la rouvrir, décision humaine. |
| T10 | **Longs jobs détachés** : `subprocess.Popen(start_new_session=True)` lancé depuis l'outil shell a produit des descripteurs invalides chez le processus petit-fils (`Fatal Python error: init_sys_streams`). Faux échec. | Lancer les runs longs (MCMC, `make check`) via `nohup cmd > log 2>&1 </dev/null &`, puis poller le log. | — |
| T11 | `nutpie`/`llvmlite >= 0.46` : pas de wheel macOS **x86_64** (machine de développement) ; arviz **1.x incompatible avec pymc 5.26** (`ImportError: concat`). | Pas de sampler nutpie ; pin `arviz>=0.22,<1` dans `pyproject.toml`. | Rouvrir si la machine passe en arm64 ou si pymc est monté de version. |
| T8 | Les branches sont empilées et il n'y a pas de `main`. | Revue difficile. | Créer `main` depuis F00 et fusionner dans l'ordre, ou ouvrir des PR empilées (décision humaine). |

## 4. Ce qui reste à faire

Ordre imposé par `features/ROADMAP.md` : la première feature `todo` dont toutes les
dépendances sont `done`. La colonne « Prérequis humain » indique ce qui bloque le **run réel**.
Le développement et les tests sur fixtures restent toujours possibles.

| ID | Feature | Dépend de | Prérequis humain | Points d'attention |
|---|---|---|---|---|
| F14 | Collecte presse | F03, F04 | Choix des flux autorisés | `news` reste `false` sans décision humaine ; fiche à reprendre (T9). |
| **F16** ✅ | Fusion, annotation, contrôle qualité | F12, F13, F15 | 300 à 500 épisodes annotés à la main ; avis juriste art. 9 | Comparer l'incidence aux priors (PRISP). |
| **F17** ✅ | Table `ml_player_match` et test anti-fuite | F16 | — | Features `as_of_ts`, `player_key` seul, oracle Python indépendant + test de mutation. |
| **F18** ✅ | Cadre d'évaluation et MLflow | F17 | — | Rolling origin par saison, métriques de calibration, bootstrap clusterisé joueur, MLflow sqlite, rapport agrégé, CLI `rugby-risk train`. |
| **F19** ✅ | Baseline Poisson par poste (M0) et priors | F18 | — | `priors.py` (constantes docs/02 centralisées), `baselines.py` (taux par poste lissés gamma-Poisson), Brier skill vs M0 global dans chaque rapport, run réel : taux 8,7–30,8/1000 h par poste. Fix data : positions allrugby résolus via `position_aliases.csv` (loader `reference.position_canonical`). |
| **F20** ✅ | Hazard en temps discret (M1) | F19 | — | `design.py` (transformations apprises sur le train, termes dégénérés écartés), `hazard.py` (GLM cloglog/logit + offset), `curves.py` + `configs/scenarios.yaml`, bootstrap joueur des courbes. Censure fin de saison exclue (S11). Réel : M1 ne bat pas encore M0 (1 saison de train). |
| **F21** ✅ | Sélection et pondération IPW | F20 | — | `selection.py` (LR L2, gate de calibration cross-fittée pente ∈ [0,8 ; 1,2], poids stabilisés tronqués, ESS), M1w via forme binomiale groupée (statsmodels ignore `freq_weights` Bernoulli, S13), hook `requires_eligible` dans le runner, 3 variantes en sensibilité. Réel : coefficients de charge à la hausse (attendu), métriques prédictives légèrement dégradées (coût variance, 1 saison). |
| F22 ✅ | Modèle hiérarchique bayésien | F21 | Revue du rapport de modèle | **Fait** : PyMC direct (pas bambi), hiérarchie non centrée unit→groupe→code, IPW par `pm.Potential`, intégration Gauss-Hermite des joueurs/équipe-saisons nouveaux, prior predictive 9/9 dans la bande 30–150, run de référence conforme §6 (R̂ 1,0064, ESS 866/899, 0 divergence, `target_accept` 0,99), baselines M0/M1/M1w relancées sur le dataset v7 (S15), revue complète générée. Décision de promotion : humaine, non demandée. |
| F23 | Challenger LightGBM et SHAP | F20 | — | Gain de log-loss en validation temporelle. |
| F30 ✅ | Simulateur de profil de charge par poste | F22 | Promotion pour lever la mention « non promu » | **Fait** : `runner.fit_final` (toutes saisons hors test gelé, mêmes filtres que les folds), artefact local `data/models/<run_id>/` (tirages de population, colonnes de features sans identifiant ni cible, transform reconstruit et vérifié car patsy n'est pas sérialisable), `rugby-risk fit-final` et `rugby-risk profile --position ...` (risque par match enchaîné et cumulé avec IC90, facteur par match, avertissement). Promotion = fichier `PROMOTION.md` écrit par un humain. |
| F24 | Modèle de gravité | F18 | — | Jours d'absence (`days_missed`), burden par poste. |
| F25 | Prédictions batch et export Supabase | F22 | Promotion manuelle du modèle | Garde-fou d'agrégation : jamais de valeur nominative. |
| F26 | API FastAPI | F25 | — | Lecture seule, agrégats uniquement. |
| F27 | Front Next.js | F26 | Compte Vercel et projet Supabase | Pédagogie, limites, scénarios. |
| F28 | Orchestration et monitoring | F10, F25 | — | Jobs hebdomadaires, dérive, calibration. |
| F29 | Model card, data card, AIPD, réentraînement | F22, F27 | Juriste | Purge des données de santé (`make purge-health`). |

Prochaine étape immédiate : **F23** (challenger gradient boosting et SHAP). Écarts connus : la fiche F14 est marquée `done` dans la ROADMAP mais ses
cases et son Journal ne sont pas remplis (T9) ; le critère « précision ≥ 0,85 » de F16
attend l'annotation humaine ; run réel F09 (audit de 100 joueurs) et parseurs
internationaux à compléter (birth_date). Crawl réel allrugby terminé le 2026-11-06 :
3 saisons × 188 matchs ; staging reconstruit, `scripts/run_pipeline.sh` rejoue le pipeline
hors-ligne (staging → entités → marts → blessures → table ML). F17 : `travel_km_14d` non
produit (stades sans coordonnées, S7) ; EWMA en forme fermée (pas de `int_player_day`).

## 5. Règles à appliquer (toutes features)

### Workflow obligatoire (`CLAUDE.md` §2)

1. Prendre la première feature `todo` de la ROADMAP dont toutes les dépendances sont `done`.
2. Lire toute la fiche et les docs qu'elle référence.
3. Passer son statut à `in_progress`.
4. Créer la branche `feat/Fxx-slug`.
5. Implémenter **seulement le périmètre** de la fiche, en respectant « Hors périmètre ».
6. Écrire les tests de la fiche avec le code. **Jamais de réseau dans les tests** : fixtures
   de `tests/fixtures/` uniquement.
7. Obtenir un `make check` vert.
8. Cocher les critères `- [x]`. Un critère non tenu est expliqué dans le **Journal** de la
   fiche.
9. Passer le statut à `done` dans la ROADMAP, dans le même commit Conventional Commits
   (`feat(Fxx): ...`), avec un `git add` ciblé.
10. Résumer en 5 lignes maximum ce qui est fait et ce qui reste ouvert.

En cas d'ambiguïté : **`docs/` fait foi pour les règles** (conformité, schéma), **la fiche
fait foi pour le périmètre**.

### Règles d'or (non négociables, `CLAUDE.md` §3)

1. **Pas de fuite temporelle** : chaque feature est calculée avec des données strictement
   antérieures au coup d'envoi (`as_of_ts`).
2. **Validation temporelle uniquement** : découpage par saison, jamais de k-fold aléatoire.
3. **RGPD art. 9** : une blessure liée à un joueur identifié est une donnée de santé. Les
   tables d'apprentissage utilisent `player_key` pseudonymisé ; l'API et le front n'exposent
   que des agrégats par poste ou groupe de postes.
4. **Respect des sources** : aucun appel réseau si `authorized: false` ; robots.txt, débit
   limité, User-Agent identifiable.
5. **Idempotence** : rejouer une partition ne crée aucun doublon (upsert sur clés
   naturelles).
6. **Lac brut immuable** : stocker avant d'analyser ; on ré-analyse sans re-collecter.
7. **Pas de ratio ACWR** comme feature centrale : charges aiguë et chronique séparées.
8. **La calibration passe avant la discrimination** : sélection des modèles sur la log-loss
   et le Brier, pas sur l'AUC.
9. **Pas de secrets dans le code** : `.env` (non commité) et `settings.py`.

### Interdits (`CLAUDE.md` §8)

- Lancer un scraping massif « pour tester ». Les runs réels passent par Dagster, sur une
  partition explicite.
- Publier ou journaliser des données de blessure nominatives.
- Modifier `docs/07-legal-rgpd.md`, ou `authorized` dans `config/sources.yaml`, sans
  demande explicite de l'humain.
- Ajouter une dépendance lourde absente de la stack sans la justifier dans le Journal.

### Conventions (`CLAUDE.md` §7, `docs/08-conventions.md`)

- Identifiants en anglais. Les commentaires et docstrings suivent la langue de chaque
  fichier.
- Fonctions pures pour l'analyse des pages et le calcul des features. Les effets de bord
  restent dans `http/` et dans les assets Dagster.
- Un parseur = un module = un fichier de tests, avec au moins 2 fixtures dont un cas limite.
  `PARSER_VERSION` est incrémenté à chaque changement de format.
- Dates en UTC timezone-aware dans le stockage ; Europe/Paris seulement à l'affichage.
- Postes : uniquement le vocabulaire de `data/reference/positions.csv`, via
  `position_aliases.csv` ou `reference.position_from_shirt`. Jamais de poste écrit en dur.
- Logs structurés, pas de `print`.

### Règles de collaboration (décisions humaines de cette session)

- Une feature à la fois, terminée (tests, Journal, ROADMAP, commit) avant de passer à la
  suivante.
- Plus petit changement complet. Chaque livraison se termine par ce qui n'a pas été vérifié
  et les risques.
- En cas d'erreur ou de doute : consulter d'abord le document de recherche à la racine Git
  (*Prédire le risque de blessure par poste et enchaînement de matchs en Top 14…*). Ce
  fichier **n'est jamais commité**.
- Sources bloquées : on garde les données obtenues à date, sans contournement (consigne LNR).
- Saison 2019-2020 incomplète : normal (COVID), pas une anomalie de collecte.

### Pièges connus

- Avant `uv` ou `make` : `export PATH="$HOME/.local/bin:$PATH"`.
- La racine Git est le dossier parent : `git add` doit cibler des chemins depuis
  `rugby-injury-risk/`.
- macOS : `sed -i ''`.
- `dagster asset materialize` : un asset par `--select`. Une partition multi-dimension
  s'écrit `J10|2024-2025`.
- Les tests d'intégration Dagster lancent un sous-processus avec
  `PYTHONPATH=repo:repo/src`, `DATA_DIR=tmp` et `cwd=repo`.
- `selectolax` : utiliser `LexborHTMLParser`.
- Le hook pre-commit prend environ 20 s ; `make check` environ 2 min 15 (voir T4).

## 6. Commandes

```bash
make check    # ruff + format + mypy + pytest (contrôle qualité obligatoire)
make seeds    # data/reference → dbt/seeds (fichiers ignorés par git)
make dbt      # seeds + dbt build (DuckDB)
make dagster  # ⚠ voir T2
uv run dagster asset materialize --select intl_staging_worldrugby --partition 2023-2024 \
  --module-name orchestration.definitions
rugby-risk raw ls --source lnr   # liste le lac brut
python tests/fixtures/worldrugby/build_fixtures.py   # régénère les fixtures internationales
```
