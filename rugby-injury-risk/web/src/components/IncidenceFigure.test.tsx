import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { IncidenceFigure } from "./IncidenceFigure";
import positionSeason from "@/data/position_season.json";
import type { PositionSeason } from "@/lib/types";

describe("IncidenceFigure", () => {
  it("le tableau de la figure 1 contient 9 lignes de postes", () => {
    const { container } = render(<IncidenceFigure rows={positionSeason as PositionSeason[]} />);
    const table = container.querySelector("table");
    expect(table).not.toBeNull();
    const caption = table?.querySelector("caption");
    expect(caption?.textContent).toMatch(/Incidence par poste/);
    const body = table?.querySelector("tbody");
    expect(within(body as HTMLElement).getAllByRole("row")).toHaveLength(9);
  });

  it("affiche un libellé accessible pour la liste de saisons", () => {
    render(<IncidenceFigure rows={positionSeason as PositionSeason[]} />);
    expect(screen.getByLabelText("Saison")).toBeInTheDocument();
  });
});
