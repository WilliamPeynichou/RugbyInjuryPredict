"use client";

import { useMemo } from "react";
import {
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { CHART, TOOLTIP_STYLE } from "@/lib/chartTheme";
import { formatAxisPercent, formatPercent } from "@/lib/format";
import { calibrationFor } from "@/lib/stats";
import type { Calibration } from "@/lib/types";
import { DataTable } from "./DataTable";
import { FigureFrame } from "./FigureFrame";
import styles from "./Figure.module.css";

/** Calibration pour le groupe « all » : probabilité prédite moyenne (X) contre observée (Y). */
export function CalibrationFigure({ rows }: { rows: readonly Calibration[] }) {
  const bins = useMemo(() => calibrationFor(rows, "all"), [rows]);
  const data = bins.map((b) => ({ x: b.p_pred_mean * 100, y: b.p_obs * 100, n: b.n, bin: b.bin }));
  const max = Math.max(...data.map((d) => Math.max(d.x, d.y))) * 1.1;
  const testSeason = bins[0]?.test_season ?? "inconnue";

  return (
    <FigureFrame
      title="Figure 3 — Calibration"
      legend={
        <>
          Chaque point est un groupe de risque prédit (« bin »). En abscisse, le risque prédit
          moyen ; en ordonnée, la fréquence observée. La diagonale indique un accord parfait. Test
          sur la saison {testSeason}, tous postes. Association statistique, non causale.
        </>
      }
      details={
        <DataTable
          caption={`Calibration, tous postes, saison ${testSeason}`}
          headers={["Groupe", "Risque prédit moyen", "Risque observé", "Effectif"]}
          rows={bins.map((b) => [
            String(b.bin),
            formatPercent(b.p_pred_mean),
            formatPercent(b.p_obs),
            String(b.n),
          ])}
        />
      }
    >
      <div className={styles.chart}>
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 16, right: 16, bottom: 24, left: 8 }}>
            <CartesianGrid stroke={CHART.stone100} />
            <XAxis
              type="number"
              dataKey="x"
              domain={[0, max]}
              tickFormatter={(v: number) => formatAxisPercent(v)}
              tick={{ fill: CHART.stone600, fontSize: 12 }}
              stroke={CHART.stone400}
              tickLine={false}
              label={{
                value: "Risque prédit moyen (%)",
                position: "insideBottom",
                offset: -12,
                style: { fill: CHART.stone600, fontSize: 12 },
              }}
            />
            <YAxis
              type="number"
              dataKey="y"
              domain={[0, max]}
              tickFormatter={(v: number) => formatAxisPercent(v)}
              tick={{ fill: CHART.stone600, fontSize: 12 }}
              stroke={CHART.stone400}
              tickLine={false}
              width={56}
              label={{
                value: "Risque observé (%)",
                angle: -90,
                position: "insideLeft",
                offset: 0,
                style: { fill: CHART.stone600, fontSize: 12 },
              }}
            />
            <ReferenceLine
              segment={[
                { x: 0, y: 0 },
                { x: max, y: max },
              ]}
              stroke={CHART.stone400}
              strokeDasharray="4 4"
            />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              formatter={(value, name) => [
                formatAxisPercent(Number(value)),
                name === "x" ? "Prédit" : "Observé",
              ]}
            />
            <Scatter data={data} fill={CHART.brand} stroke={CHART.brand} isAnimationActive={false} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </FigureFrame>
  );
}
