import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DataTable } from "./DataTable";

describe("DataTable", () => {
  it("rend une caption et des en-têtes de colonnes", () => {
    render(<DataTable caption="Essai" headers={["Poste", "Valeur"]} rows={[["Centre", "1,0"]]} />);
    expect(screen.getByRole("table", { name: "Essai" })).toBeInTheDocument();
    expect(screen.getAllByRole("columnheader")).toHaveLength(2);
    expect(screen.getByRole("rowheader", { name: "Centre" })).toBeInTheDocument();
  });
});
