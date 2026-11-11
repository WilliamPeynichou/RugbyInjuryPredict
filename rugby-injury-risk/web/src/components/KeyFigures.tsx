import { formatInteger, formatRate } from "@/lib/format";
import type { HeadlineStats } from "@/lib/stats";
import styles from "./KeyFigures.module.css";

export function KeyFigures({ stats }: { stats: HeadlineStats }) {
  const items = [
    { value: formatInteger(stats.n_seasons), label: "Saisons analysées", text: false },
    { value: formatInteger(stats.n_positions), label: "Postes", text: false },
    { value: formatInteger(stats.exposure_hours), label: "Heures de match analysées", text: false },
    {
      text: true,
      value: stats.top_position_label,
      label: "Poste à l'incidence la plus élevée",
      sub: `${formatRate(stats.top_incidence)} blessures / 1 000 h`,
    },
  ];
  return (
    <dl className={styles.grid}>
      {items.map((it) => (
        <div key={it.label} className={styles.item}>
          <dt className={styles.label}>{it.label}</dt>
          <dd className={it.text ? styles.valueText : styles.value}>{it.value}</dd>
          {it.sub ? <dd className={styles.sub}>{it.sub}</dd> : null}
        </div>
      ))}
    </dl>
  );
}
