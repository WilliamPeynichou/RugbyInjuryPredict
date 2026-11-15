// Types des données agrégées publiques (voir scripts/build-data.mjs).
// Aucun identifiant joueur n'existe dans ces types.

export type PositionCode =
  | "PROP"
  | "HOOKER"
  | "LOCK"
  | "BACK_ROW"
  | "SCRUM_HALF"
  | "FLY_HALF"
  | "CENTRE"
  | "WING"
  | "FULLBACK";

export interface PositionSeason {
  season_id: string;
  position_code: PositionCode;
  position_group: string;
  incidence_per_1000h: number;
  incidence_low90: number;
  incidence_high90: number;
  injuries_count_bucket: string;
  exposure_hours: number;
  n_matches_played: number;
  n_players_support: number;
}

export interface PositionCurve {
  position_code: PositionCode;
  scenario: string;
  n_consecutive: number;
  p_mean: number;
  p_low90: number;
  p_high90: number;
  cum_mean: number;
  cum_low90: number;
  cum_high90: number;
  n_players_support: number;
}

export interface Calibration {
  test_season: string;
  position_group: string;
  bin: number;
  p_pred_mean: number;
  p_obs: number;
  n: number;
}

export interface ModelRecord {
  model_name: string;
  role: string;
  promoted: boolean;
  test_season: string;
  dataset_version: string;
  brier: number;
  brier_low90: number;
  brier_high90: number;
  brier_skill: number;
  logloss: number;
  auc_roc: number;
  calib_slope: number;
}
