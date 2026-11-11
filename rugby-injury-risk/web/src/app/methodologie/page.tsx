import { CalibrationFigure } from "@/components/CalibrationFigure";
import { formatScore } from "@/lib/format";
import calibration from "@/data/calibration.json";
import modelRegistry from "@/data/model_registry.json";
import type { Calibration, ModelRecord } from "@/lib/types";
import styles from "./page.module.css";

export const metadata = {
  title: "Méthodologie — Risque de blessure par poste",
};

const yesNo = (b: boolean) => (b ? "Oui" : "Non");

export default function MethodologyPage() {
  const models = modelRegistry as ModelRecord[];
  const cal = calibration as Calibration[];

  return (
    <div className={styles.page}>
      <header className={styles.intro}>
        <h1 className={styles.title}>Méthodologie</h1>
      </header>

      <section className={styles.prose} aria-labelledby="sources">
        <h2 id="sources" className={styles.h2}>D&apos;où viennent les données</h2>
        <p>
          Les données proviennent de sources publiques, à partir des feuilles de match du Top 14.
          Elles sont agrégées par poste et par saison avant publication.
        </p>
        <h2 className={styles.h2}>Comment une blessure est comptée</h2>
        <p>
          Une blessure est comptée lorsqu&apos;elle entraîne au moins 2 matchs d&apos;absence. Elle est
          reconstruite à partir des feuilles de match, et n&apos;a pas été vérifiée à la main : des
          blessures courtes peuvent manquer.
        </p>
        <h2 className={styles.h2}>Ce que montre le site</h2>
        <p>
          Le site montre des ordres de grandeur par poste. Il ne fait jamais de pronostic sur un
          joueur et ne remplace pas l&apos;avis du staff médical.
        </p>
      </section>

      <section className={styles.block} aria-labelledby="modeles">
        <h2 id="modeles" className={styles.h2}>Modèles comparés</h2>
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <caption className={styles.caption}>
              Performances sur la saison de test, depuis le registre public
            </caption>
            <thead>
              <tr>
                <th scope="col">Modèle</th>
                <th scope="col">Rôle</th>
                <th scope="col">Log-loss</th>
                <th scope="col">Brier</th>
                <th scope="col">Brier skill</th>
                <th scope="col">AUC</th>
                <th scope="col">Pente de calibration</th>
                <th scope="col">Promu</th>
              </tr>
            </thead>
            <tbody>
              {models.map((m) => (
                <tr key={m.model_name + m.role}>
                  <th scope="row">{m.model_name}</th>
                  <td>{m.role}</td>
                  <td>{formatScore(m.logloss)}</td>
                  <td>{formatScore(m.brier)}</td>
                  <td>{formatScore(m.brier_skill)}</td>
                  <td>{formatScore(m.auc_roc)}</td>
                  <td>{formatScore(m.calib_slope)}</td>
                  <td>{yesNo(m.promoted)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className={styles.block}>
        <CalibrationFigure rows={cal} />
      </div>

      <section className={styles.prose} aria-labelledby="limites">
        <h2 id="limites" className={styles.h2}>Limites</h2>
        <ul className={styles.list}>
          <li>Les blessures courtes (moins de 2 matchs d&apos;absence) sont sous-déclarées.</li>
          <li>La validation repose sur un seul découpage temporel.</li>
          <li>
            Biais de sélection : les joueurs fatigués peuvent être mis au repos, ce qui fausse les
            comparaisons.
          </li>
          <li>Les résultats sont une association statistique, jamais une cause.</li>
          <li>
            Les données sont agrégées : aucun joueur n&apos;est identifiable, et le site n&apos;utilise pas
            de cookie.
          </li>
        </ul>
      </section>
    </div>
  );
}
