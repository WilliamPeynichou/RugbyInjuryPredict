import { describe, expect, it } from "vitest";
import calibration from "@/data/calibration.json";
import modelRegistry from "@/data/model_registry.json";
import positionCurve from "@/data/position_curve.json";
import positionSeason from "@/data/position_season.json";
import {
  ALL_SEASONS,
  calibrationFor,
  curveFor,
  headlineStats,
  listSeasons,
  principalModel,
  summarizeByPosition,
  weightedMean,
} from "./stats";
import type { Calibration, ModelRecord, PositionCurve, PositionSeason } from "./types";

const base = {
  position_group: "x",
  injuries_count_bucket: "",
  n_matches_played: 0,
  n_players_support: 10,
};

// Petit exemple calculé à la main : poste PROP sur deux saisons.
//   saison A : taux 10, bornes [5 ; 15], heures 100
//   saison B : taux 20, bornes [10 ; 30], heures 300
// Moyenne pondérée = (10*100 + 20*300) / 400 = 17,5
// Bornes basses   = (5*100 + 10*300) / 400 = 8,75
// Bornes hautes   = (15*100 + 30*300) / 400 = 26,25
const sample: PositionSeason[] = [
  { ...base, season_id: "2022-2023", position_code: "PROP", incidence_per_1000h: 10, incidence_low90: 5, incidence_high90: 15, exposure_hours: 100 },
  { ...base, season_id: "2023-2024", position_code: "PROP", incidence_per_1000h: 20, incidence_low90: 10, incidence_high90: 30, exposure_hours: 300 },
  { ...base, season_id: "2022-2023", position_code: "WING", incidence_per_1000h: 4, incidence_low90: 2, incidence_high90: 6, exposure_hours: 50 },
  { ...base, season_id: "2023-2024", position_code: "WING", incidence_per_1000h: 8, incidence_low90: 4, incidence_high90: 12, exposure_hours: 50 },
];

describe("weightedMean", () => {
  it("calcule la moyenne pondérée d'un petit exemple", () => {
    expect(weightedMean([10, 20], [100, 300])).toBeCloseTo(17.5, 10);
  });

  it("refuse des poids nuls", () => {
    expect(() => weightedMean([1], [0])).toThrow();
  });
});

describe("summarizeByPosition", () => {
  it("pondère les saisons par les heures, bornes incluses", () => {
    const prop = summarizeByPosition(sample, ALL_SEASONS).find((s) => s.position_code === "PROP");
    expect(prop?.incidence).toBeCloseTo(17.5, 10);
    expect(prop?.incidence_low90).toBeCloseTo(8.75, 10);
    expect(prop?.incidence_high90).toBeCloseTo(26.25, 10);
    expect(prop?.exposure_hours).toBe(400);
  });

  it("filtre par saison et renvoie les valeurs exactes", () => {
    const prop = summarizeByPosition(sample, "2023-2024").find((s) => s.position_code === "PROP");
    expect(prop?.incidence).toBe(20);
    expect(prop?.n_seasons).toBe(1);
  });

  it("liste les saisons distinctes triées", () => {
    expect(listSeasons(sample)).toEqual(["2022-2023", "2023-2024"]);
  });
});

describe("headlineStats", () => {
  it("calcule les chiffres clés depuis les données réelles", () => {
    const rows = positionSeason as PositionSeason[];
    const h = headlineStats(rows);
    expect(h.n_seasons).toBe(3);
    expect(h.n_positions).toBe(9);
    const sum = rows.reduce((a, r) => a + r.exposure_hours, 0);
    expect(h.exposure_hours).toBeCloseTo(sum, 6);
  });
});

describe("curveFor", () => {
  it("renvoie 16 points triés pour un poste", () => {
    const pts = curveFor(positionCurve as PositionCurve[], "BACK_ROW", "median");
    expect(pts).toHaveLength(16);
    expect(pts.map((p) => p.n_consecutive)).toEqual([...Array(16).keys()]);
  });

  it("lève une erreur si la courbe est incomplète", () => {
    expect(() => curveFor([], "PROP", "median")).toThrow();
  });
});

describe("modèle principal et calibration", () => {
  it("trouve le modèle de rôle principale", () => {
    const m = principalModel(modelRegistry as ModelRecord[]);
    expect(m?.role).toBe("principale");
    expect(typeof m?.promoted).toBe("boolean");
  });

  it("filtre la calibration du groupe all, triée par bin", () => {
    const rows = calibrationFor(calibration as Calibration[], "all");
    expect(rows.length).toBeGreaterThan(0);
    expect(rows.map((r) => r.bin)).toEqual([...rows.map((r) => r.bin)].sort((a, b) => a - b));
  });
});
