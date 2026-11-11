import { CurveFigure } from "@/components/CurveFigure";
import { IncidenceFigure } from "@/components/IncidenceFigure";
import { KeyFigures } from "@/components/KeyFigures";
import { NotPromotedNotice } from "@/components/NotPromotedNotice";
import styles from "./page.module.css";
import positionSeason from "@/data/position_season.json";
import positionCurve from "@/data/position_curve.json";
import modelRegistry from "@/data/model_registry.json";
import { headlineStats } from "@/lib/stats";
import type { ModelRecord, PositionCurve, PositionSeason } from "@/lib/types";

export default function HomePage() {
  const seasons = positionSeason as PositionSeason[];
  const curves = positionCurve as PositionCurve[];
  const models = modelRegistry as ModelRecord[];
  const stats = headlineStats(seasons);

  return (
    <div className={styles.page}>
      <header className={styles.intro}>
        <h1 className={styles.title}>Risque de blessure par poste en Top 14</h1>
        <p className={styles.lede}>
          Blessures entraînant au moins 2 matchs d&apos;absence, saisons 2022 à 2025.
        </p>
      </header>

      <KeyFigures stats={stats} />

      <div className={styles.block}>
        <IncidenceFigure rows={seasons} />
      </div>

      <div className={styles.block}>
        <NotPromotedNotice models={models} />
        <CurveFigure curves={curves} />
      </div>
    </div>
  );
}
