// Échoue si un fichier de web/src ou web/.next contient un identifiant interdit.
import { readdirSync, readFileSync, statSync, existsSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const FORBIDDEN = ["player_key", "player_id", "full_name", "birth_date"];
const ROOTS = ["src", ".next"];

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) yield* walk(p);
    else yield p;
  }
}

const hits = [];
let scanned = 0;
for (const root of ROOTS) {
  const abs = join(webRoot, root);
  if (!existsSync(abs)) continue;
  for (const file of walk(abs)) {
    scanned++;
    const text = readFileSync(file, "latin1");
    for (const term of FORBIDDEN) {
      if (text.includes(term)) hits.push(`${relative(webRoot, file)} : « ${term} »`);
    }
  }
}

if (hits.length > 0) {
  console.error("check:privacy ÉCHEC — identifiants interdits trouvés :");
  for (const h of hits) console.error(`  ${h}`);
  process.exit(1);
}
console.log(`check:privacy OK — ${scanned} fichiers analysés, aucun identifiant interdit.`);
