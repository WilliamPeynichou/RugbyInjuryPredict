import type { ReactNode } from "react";
import styles from "./Figure.module.css";

/** Cadre commun : titre, figure, légende sous la figure, données dépliables. */
export function FigureFrame({
  title,
  legend,
  details,
  children,
}: {
  title: string;
  legend: ReactNode;
  details: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className={styles.figure} aria-labelledby={`${slug(title)}-title`}>
      <h2 id={`${slug(title)}-title`} className={styles.title}>
        {title}
      </h2>
      {children}
      <p className={styles.legend}>{legend}</p>
      <details className={styles.details}>
        <summary>Voir les données</summary>
        {details}
      </details>
    </section>
  );
}

function slug(s: string): string {
  return s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}
