// Formats français. 1 décimale maximum pour les % et les taux.
const NUMBER_1 = new Intl.NumberFormat("fr-FR", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});
const NUMBER_3 = new Intl.NumberFormat("fr-FR", {
  minimumFractionDigits: 3,
  maximumFractionDigits: 3,
});
const INTEGER = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });

/** Probabilité (0 à 1) -> "1,2 %". */
export function formatPercent(probability: number): string {
  return `${NUMBER_1.format(probability * 100)} %`;
}

/** Taux (blessures pour 1 000 h) -> "18,7". */
export function formatRate(rate: number): string {
  return NUMBER_1.format(rate);
}

/** Intervalle de deux taux -> "[13,0 ; 26,2]". */
export function formatRateInterval(low: number, high: number): string {
  return `[${formatRate(low)} ; ${formatRate(high)}]`;
}

/** Intervalle de deux probabilités -> "[0,7 % ; 1,3 %]". */
export function formatPercentInterval(low: number, high: number): string {
  return `[${formatPercent(low)} ; ${formatPercent(high)}]`;
}

/** Score de modèle (Brier, log-loss, AUC, pente) : 3 décimales. */
export function formatScore(value: number): string {
  return NUMBER_3.format(value);
}

/** Pourcentage d'axe déjà exprimé en points (3,0 -> "3,0 %"). */
export function formatAxisPercent(points: number): string {
  return `${NUMBER_1.format(points)} %`;
}

/** Entier, ex. nombre de saisons, heures. */
export function formatInteger(value: number): string {
  return INTEGER.format(value);
}
