import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { NotPromotedNotice } from "./NotPromotedNotice";
import type { ModelRecord } from "@/lib/types";

const model = (promoted: boolean): ModelRecord => ({
  model_name: "m2_hierarchical",
  role: "principale",
  promoted,
  test_season: "2024-2025",
  dataset_version: "x",
  brier: 0.01,
  brier_low90: 0.01,
  brier_high90: 0.02,
  brier_skill: 0,
  logloss: 0.1,
  auc_roc: 0.5,
  calib_slope: 0,
});

describe("NotPromotedNotice", () => {
  it("apparaît si le modèle principal n'est pas promu", () => {
    render(<NotPromotedNotice models={[model(false)]} />);
    expect(screen.getByText(/Modèle exploratoire, non promu/)).toBeInTheDocument();
  });

  it("disparaît si le modèle principal est promu", () => {
    const { container } = render(<NotPromotedNotice models={[model(true)]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
