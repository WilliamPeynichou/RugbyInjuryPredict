import { describe, expect, it } from "vitest";
import {
  formatInteger,
  formatPercent,
  formatPercentInterval,
  formatRate,
  formatRateInterval,
  formatScore,
} from "./format";

// Espace insécable fine/normal selon ICU : on normalise les espaces avant comparaison.
const norm = (s: string) => s.replace(/\s/g, " ");

describe("format", () => {
  it("formate une probabilité en pourcentage à 1 décimale", () => {
    expect(norm(formatPercent(0.0123))).toBe("1,2 %");
    expect(norm(formatPercent(0.1))).toBe("10,0 %");
  });

  it("formate un taux à 1 décimale, sans plus", () => {
    expect(formatRate(18.744142)).toBe("18,7");
    expect(formatRate(28.996)).toBe("29,0");
  });

  it("formate un intervalle de taux", () => {
    expect(norm(formatRateInterval(13.03, 26.18))).toBe("[13,0 ; 26,2]");
  });

  it("formate un intervalle de probabilités", () => {
    expect(norm(formatPercentInterval(0.0071, 0.0134))).toBe("[0,7 % ; 1,3 %]");
  });

  it("formate un score à 3 décimales et un entier sans décimale", () => {
    expect(formatScore(0.0176907)).toBe("0,018");
    expect(norm(formatInteger(6567.5))).toBe("6 568");
  });
});
