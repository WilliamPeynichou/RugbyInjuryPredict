"use client";

import { useId, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ErrorBar,
  Tooltip,
  XAxis,
  YAxis,
  ResponsiveContainer,
} from "recharts";
import { CHART, TOOLTIP_STYLE } from "@/lib/chartTheme";
import { formatInteger, formatRate, formatRateInterval } from "@/lib/format";
import {
  ALL_SEASONS,
  listSeasons,
  summarizeByPosition,
  type PositionSummary,
  type SeasonChoice,
} from "@/lib/stats";
import type { PositionSeason } from "@/lib/types";
import { DataTable } from "./DataTable";
import { FigureFrame } from "./FigureFrame";
import styles from "./Figure.module.css";

interface BarDatum {
  label: string;
  incidence: number;
  errY: [number, number];
}

function toBarData(summaries: PositionSummary[]): BarDatum[] {
  return summaries.map((s) => ({
    label: s.label,
    incidence: s.incidence,
    // Recharts attend les écarts [bas, haut] et non les bornes.
    errY: [s.incidence - s.incidence_low90, s.incidence_high90 - s.incidence],
  }));
}

export function IncidenceFigure({ rows }: { rows: readonly PositionSeason[] }) {
  const seasons = useMemo(() => listSeasons(rows), [rows]);
  const [season, setSeason] = useState<SeasonChoice>(ALL_SEASONS);
  const selectId = useId();

  const summaries = useMemo(() => summarizeByPosition(rows, season), [rows, season]);
  const data = useMemo(() => toBarData(summaries), [summaries]);
  const yMax = Math.max(...summaries.map((s) => s.incidence_high90)) * 1.08;
  const period = `saisons ${seasons[0]} à ${seasons[seasons.length - 1]}`;
  const scopeLabel =
    season === ALL_SEASONS ? `${period}, moyenne pondérée par heures` : `saison ${season}`;

  return (
    <FigureFrame
      title="Figure 1 — Incidence observée par poste"
      legend={
        <>
          Barres : incidence moyenne par poste ({scopeLabel}). Traits : intervalle à 90 %. Le
          nombre de joueurs de support varie selon le poste (voir les données). Association
          statistique, non causale.
        </>
      }
      details={
        <DataTable
          caption={`Incidence par poste, ${scopeLabel}`}
          headers={[
            "Poste",
            "Incidence, blessures / 1 000 h",
            "Intervalle à 90 %",
            "Heures de match",
            "Joueurs de support (min–max)",
          ]}
          rows={summaries.map((s) => [
            s.label,
            formatRate(s.incidence),
            formatRateInterval(s.incidence_low90, s.incidence_high90),
            formatInteger(s.exposure_hours),
            s.support_min === s.support_max
              ? String(s.support_min)
              : `${s.support_min}–${s.support_max}`,
          ])}
        />
      }
    >
      <div className={styles.controls}>
        <div className={styles.field}>
          <label htmlFor={selectId} className={styles.label}>
            Saison
          </label>
          <select
            id={selectId}
            className={styles.select}
            value={season}
            onChange={(e) => setSeason(e.target.value)}
          >
            <option value={ALL_SEASONS}>Toutes</option>
            {seasons.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className={styles.chart}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 16, right: 16, bottom: 8, left: 8 }}>
            <CartesianGrid vertical={false} stroke={CHART.stone100} />
            <XAxis
              dataKey="label"
              tick={{ fill: CHART.stone600, fontSize: 12 }}
              stroke={CHART.stone400}
              interval={0}
              tickLine={false}
            />
            <YAxis
              domain={[0, yMax]}
              tick={{ fill: CHART.stone600, fontSize: 12 }}
              stroke={CHART.stone400}
              tickLine={false}
              width={56}
              label={{
                value: "Blessures pour 1 000 heures de match",
                angle: -90,
                position: "insideLeft",
                offset: 0,
                style: { fill: CHART.stone600, fontSize: 12 },
              }}
              tickFormatter={(v: number) => formatRate(v)}
            />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              formatter={(value) => [formatRate(Number(value)), "Incidence"]}
            />
            <Bar dataKey="incidence" fill={CHART.brand} barSize={36} isAnimationActive={false}>
              <ErrorBar dataKey="errY" direction="y" width={6} stroke={CHART.stone800} strokeWidth={1} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </FigureFrame>
  );
}
