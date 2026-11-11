"use client";

import { useId, useMemo, useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { CHART, TOOLTIP_STYLE } from "@/lib/chartTheme";
import { formatAxisPercent, formatPercent, formatPercentInterval } from "@/lib/format";
import { POSITIONS, positionLabel } from "@/lib/positions";
import { curveFor } from "@/lib/stats";
import type { PositionCode, PositionCurve } from "@/lib/types";
import { DataTable } from "./DataTable";
import { FigureFrame } from "./FigureFrame";
import styles from "./Figure.module.css";

// Recharts trace en points de pourcentage : valeurs x100 pour l'axe en %.
export function CurveFigure({ curves }: { curves: readonly PositionCurve[] }) {
  const [position, setPosition] = useState<PositionCode>("PROP");
  const selectId = useId();
  const points = useMemo(() => curveFor(curves, position, "median"), [curves, position]);
  const data = points.map((p) => ({
    n: p.n_consecutive,
    mean: p.p_mean * 100,
    band: [p.p_low90 * 100, p.p_high90 * 100] as [number, number],
  }));
  const yMax = Math.max(...points.map((p) => p.p_high90 * 100)) * 1.1;
  const label = positionLabel(position);
  const support = points[0].n_players_support;

  return (
    <FigureFrame
      title="Figure 2 — Risque estimé au prochain match selon le nombre de matchs enchaînés"
      legend={
        <>
          Trait : risque estimé au prochain match pour le poste « {label} », scénario médian, en
          fonction des matchs consécutifs déjà joués. Bande : intervalle à 90 %. Joueurs de
          support : {support}. Association statistique, non causale.
        </>
      }
      details={
        <DataTable
          caption={`Risque au prochain match, poste « ${label} », scénario médian`}
          headers={["Matchs consécutifs", "Risque", "Intervalle à 90 %"]}
          rows={points.map((p) => [
            String(p.n_consecutive),
            formatPercent(p.p_mean),
            formatPercentInterval(p.p_low90, p.p_high90),
          ])}
        />
      }
    >
      <div className={styles.controls}>
        <div className={styles.field}>
          <label htmlFor={selectId} className={styles.label}>
            Poste
          </label>
          <select
            id={selectId}
            className={styles.select}
            value={position}
            onChange={(e) => setPosition(e.target.value as PositionCode)}
          >
            {POSITIONS.map((p) => (
              <option key={p.code} value={p.code}>
                {p.label}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className={styles.chart}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 16, right: 16, bottom: 24, left: 8 }}>
            <CartesianGrid vertical={false} stroke={CHART.stone100} />
            <XAxis
              dataKey="n"
              type="number"
              domain={[0, 15]}
              ticks={[0, 3, 6, 9, 12, 15]}
              allowDecimals={false}
              tick={{ fill: CHART.stone600, fontSize: 12 }}
              stroke={CHART.stone400}
              tickLine={false}
              label={{
                value: "Matchs consécutifs déjà joués",
                position: "insideBottom",
                offset: -12,
                style: { fill: CHART.stone600, fontSize: 12 },
              }}
            />
            <YAxis
              domain={[0, yMax]}
              tick={{ fill: CHART.stone600, fontSize: 12 }}
              stroke={CHART.stone400}
              tickLine={false}
              width={56}
              tickFormatter={(v: number) => formatAxisPercent(v)}
              label={{
                value: "Risque au prochain match (%)",
                angle: -90,
                position: "insideLeft",
                offset: 0,
                style: { fill: CHART.stone600, fontSize: 12 },
              }}
            />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              labelFormatter={(v) => `${v} matchs consécutifs`}
              formatter={(value, name) =>
                name === "band" ? ["", "Intervalle à 90 %"] : [formatPercent(Number(value) / 100), "Risque"]
              }
            />
            <Area
              dataKey="band"
              stroke="none"
              fill={CHART.brand}
              fillOpacity={0.18}
              isAnimationActive={false}
              name="band"
            />
            <Line
              dataKey="mean"
              type="linear"
              stroke={CHART.brand}
              strokeWidth={1.5}
              dot={{ r: 2.5, fill: CHART.brand, stroke: CHART.brand }}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </FigureFrame>
  );
}
