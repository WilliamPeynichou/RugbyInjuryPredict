import type { ModelRecord } from "@/lib/types";
import { principalModel } from "@/lib/stats";
import styles from "./NotPromotedNotice.module.css";

/**
 * Encadré affiché si le modèle de rôle « principale » n'est pas promu.
 * Le booléen vient des données : rien n'est codé en dur.
 */
export function NotPromotedNotice({ models }: { models: readonly ModelRecord[] }) {
  const model = principalModel(models);
  if (!model || model.promoted) return null;
  return (
    <aside className={styles.notice} role="note" aria-label="Statut du modèle">
      <p>
        <strong>Modèle exploratoire, non promu :</strong> il n&apos;a pas passé la validation. Aucune
        hausse du risque avec l&apos;enchaînement des matchs n&apos;est établie sur 3 saisons.
      </p>
    </aside>
  );
}
