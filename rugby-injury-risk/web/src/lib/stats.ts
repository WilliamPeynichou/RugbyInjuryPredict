import { POSITIONS, positionLabel } from "./positions";
import type {
  Calibration,
  ModelRecord,
  PositionCode,
  PositionCurve,
  PositionSeason,
} from "./types";

/** Moyenne pondérée. Lève une erreur si les poids sont nuls ou incohérents. */
export function weightedMean(values: readonly number[], weights: readonly number[]): number {
  if (values.length !== weights.length) throw new Error("Longueurs différentes");
  if (values.length === 0) throw new Error("Aucune valeur");
  let num = 0;
  let den = 0;
  for (let i = 0; i < values.length; i++) {
    num += values[i] * weights[i];
    den += weights[i];
  }
  if (den <= 0) throw new Error("Somme des poids nulle");
  return num / den;
}

export const ALL_SEASONS = "Toutes" as const;
export type SeasonChoice = typeof ALL_SEASONS | string;

/** Saisons distinctes, triées. */
export function listSeasons(rows: readonly PositionSeason[]): string[] {
  return [...new Set(rows.map((r) => r.season_id))].sort();
}

export interface PositionSummary {
  position_code: PositionCode;
  label: string;
  incidence: number;
  incidence_low90: number;
  incidence_high90: number;
  exposure_hours: number;
  support_min: number;
  support_max: number;
  n_seasons: number;
}

/**
 * Résumé par poste.
 * - "Toutes" : moyenne des saisons pondérée par exposure_hours (bornes incluses).
 * - une saison : valeurs exactes de cette saison.
 * Seuls les postes présents dans les données sont renvoyés, dans l'ordre d'affichage.
 * Aucune valeur n'est inventée pour un poste absent.
 */
export function summarizeByPosition(
  rows: readonly PositionSeason[],
  season: SeasonChoice,
): PositionSummary[] {
  const selected = season === ALL_SEASONS ? rows : rows.filter((r) => r.season_id === season);
  return POSITIONS.filter(({ code }) => selected.some((r) => r.position_code === code)).map(
    ({ code }) => {
      const mine = selected.filter((r) => r.position_code === code);
      const weights = mine.map((r) => r.exposure_hours);
      const support = mine.map((r) => r.n_players_support);
      return {
        position_code: code,
        label: positionLabel(code),
        incidence: weightedMean(mine.map((r) => r.incidence_per_1000h), weights),
        incidence_low90: weightedMean(mine.map((r) => r.incidence_low90), weights),
        incidence_high90: weightedMean(mine.map((r) => r.incidence_high90), weights),
        exposure_hours: mine.reduce((acc, r) => acc + r.exposure_hours, 0),
        support_min: Math.min(...support),
        support_max: Math.max(...support),
        n_seasons: mine.length,
      };
    },
  );
}

export interface HeadlineStats {
  n_seasons: number;
  n_positions: number;
  exposure_hours: number;
  top_position: PositionCode;
  top_position_label: string;
  top_incidence: number;
}

/** Chiffres clés de la page d'accueil, calculés depuis les données. */
export function headlineStats(rows: readonly PositionSeason[]): HeadlineStats {
  const summaries = summarizeByPosition(rows, ALL_SEASONS);
  const top = summaries.reduce((best, s) => (s.incidence > best.incidence ? s : best));
  return {
    n_seasons: listSeasons(rows).length,
    n_positions: new Set(rows.map((r) => r.position_code)).size,
    exposure_hours: rows.reduce((acc, r) => acc + r.exposure_hours, 0),
    top_position: top.position_code,
    top_position_label: top.label,
    top_incidence: top.incidence,
  };
}

export interface CurvePoint {
  n_consecutive: number;
  p_mean: number;
  p_low90: number;
  p_high90: number;
  n_players_support: number;
}

/**
 * Courbe d'un poste pour un scénario : 16 points (0 à 15), triés.
 * Lève une erreur si la courbe est incomplète.
 */
export function curveFor(
  curves: readonly PositionCurve[],
  position: PositionCode,
  scenario = "median",
): CurvePoint[] {
  const points = curves
    .filter((c) => c.position_code === position && c.scenario === scenario)
    .map((c) => ({
      n_consecutive: c.n_consecutive,
      p_mean: c.p_mean,
      p_low90: c.p_low90,
      p_high90: c.p_high90,
      n_players_support: c.n_players_support,
    }))
    .sort((a, b) => a.n_consecutive - b.n_consecutive);
  if (points.length !== 16) {
    throw new Error(`Courbe incomplète pour ${position} (${points.length} points)`);
  }
  return points;
}

/** Modèle de rôle « principale », ou undefined. */
export function principalModel(models: readonly ModelRecord[]): ModelRecord | undefined {
  return models.find((m) => m.role === "principale");
}

/** Lignes de calibration pour un groupe de postes, triées par bin. */
export function calibrationFor(rows: readonly Calibration[], group: string): Calibration[] {
  return rows.filter((r) => r.position_group === group).sort((a, b) => a.bin - b.bin);
}
