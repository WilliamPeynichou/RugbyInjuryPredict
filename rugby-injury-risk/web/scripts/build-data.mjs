// Lit les 4 CSV publics agrégés et écrit 4 JSON dans src/data/.
// Node pur, sans dépendance. Aucun identifiant joueur n'est lu ni écrit.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const webRoot = join(here, "..");
const publicDir = join(webRoot, "..", "reports", "public_preview");
const outDir = join(webRoot, "src", "data");

// Colonnes autorisées par fichier : toute autre colonne est ignorée.
const SCHEMAS = {
  "pred_position_season.csv": {
    out: "position_season.json",
    columns: [
      "season_id", "position_code", "position_group", "incidence_per_1000h",
      "incidence_low90", "incidence_high90", "injuries_count_bucket",
      "exposure_hours", "n_matches_played", "n_players_support",
    ],
    numeric: [
      "incidence_per_1000h", "incidence_low90", "incidence_high90",
      "exposure_hours", "n_matches_played", "n_players_support",
    ],
  },
  "pred_position_curve.csv": {
    out: "position_curve.json",
    columns: [
      "position_code", "scenario", "n_consecutive", "p_mean", "p_low90",
      "p_high90", "cum_mean", "cum_low90", "cum_high90", "n_players_support",
    ],
    numeric: [
      "n_consecutive", "p_mean", "p_low90", "p_high90", "cum_mean",
      "cum_low90", "cum_high90", "n_players_support",
    ],
  },
  "calibration_public.csv": {
    out: "calibration.json",
    columns: ["test_season", "position_group", "bin", "p_pred_mean", "p_obs", "n"],
    numeric: ["bin", "p_pred_mean", "p_obs", "n"],
  },
  "model_registry_public.csv": {
    out: "model_registry.json",
    columns: [
      "model_name", "role", "promoted", "test_season", "dataset_version",
      "brier", "brier_low90", "brier_high90", "brier_skill", "logloss",
      "auc_roc", "calib_slope",
    ],
    numeric: [
      "brier", "brier_low90", "brier_high90", "brier_skill", "logloss",
      "auc_roc", "calib_slope",
    ],
  },
};

// Parseur CSV minimal : gère les guillemets et les virgules entre guillemets.
function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') inQuotes = false;
      else field += c;
    } else if (c === '"') inQuotes = true;
    else if (c === ",") { row.push(field); field = ""; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field); field = "";
      if (row.length > 1 || row[0] !== "") rows.push(row);
      row = [];
    } else field += c;
  }
  if (field !== "" || row.length > 0) { row.push(field); rows.push(row); }
  const [header, ...body] = rows;
  return body.map((r) => Object.fromEntries(header.map((h, j) => [h, r[j] ?? ""])));
}

function convert(record, schema) {
  const out = {};
  for (const col of schema.columns) {
    const raw = record[col];
    if (raw === undefined) throw new Error(`Colonne absente : ${col}`);
    if (schema.numeric.includes(col)) {
      if (raw === "") { out[col] = null; continue; }
      const n = Number(raw);
      if (!Number.isFinite(n)) throw new Error(`Valeur non numérique pour ${col} : ${raw}`);
      out[col] = n;
    } else if (col === "promoted") {
      out[col] = raw === "true";
    } else {
      out[col] = raw;
    }
  }
  return out;
}

mkdirSync(outDir, { recursive: true });
for (const [file, schema] of Object.entries(SCHEMAS)) {
  const text = readFileSync(join(publicDir, file), "utf8");
  const records = parseCsv(text);
  if (records.length === 0) throw new Error(`Fichier vide : ${file}`);
  const data = records.map((r) => convert(r, schema));
  writeFileSync(join(outDir, schema.out), JSON.stringify(data, null, 2) + "\n", "utf8");
  console.log(`${file} -> src/data/${schema.out} (${data.length} lignes)`);
}
