import type { PositionCode } from "./types";

// Ordre d'affichage : avants puis arrières.
export const POSITIONS: ReadonlyArray<{ code: PositionCode; label: string }> = [
  { code: "PROP", label: "Pilier" },
  { code: "HOOKER", label: "Talonneur" },
  { code: "LOCK", label: "Deuxième ligne" },
  { code: "BACK_ROW", label: "Troisième ligne" },
  { code: "SCRUM_HALF", label: "Demi de mêlée" },
  { code: "FLY_HALF", label: "Demi d'ouverture" },
  { code: "CENTRE", label: "Centre" },
  { code: "WING", label: "Ailier" },
  { code: "FULLBACK", label: "Arrière" },
];

export function positionLabel(code: PositionCode): string {
  const found = POSITIONS.find((p) => p.code === code);
  if (!found) throw new Error(`Poste inconnu : ${code}`);
  return found.label;
}
