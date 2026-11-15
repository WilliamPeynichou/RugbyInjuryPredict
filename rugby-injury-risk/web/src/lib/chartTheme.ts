// Couleurs des graphiques : mêmes valeurs que les variables CSS de globals.css.
// Les attributs SVG ne résolvent pas var(), d'où les constantes.
export const CHART = {
  brand: "#6b7c5c",
  stone100: "#e8e4d8",
  stone400: "#a09a8a",
  stone600: "#6b6558",
  stone800: "#3a3730",
  cream: "#f3f0e8",
} as const;

export const TOOLTIP_STYLE = {
  background: CHART.cream,
  border: `1px solid ${CHART.stone400}`,
  borderRadius: 0,
  color: CHART.stone800,
  fontSize: 13,
} as const;
