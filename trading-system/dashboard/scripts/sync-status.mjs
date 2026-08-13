// Copies the latest cockpit status into public/ so the dashboard can fetch it.
// Runs automatically before `npm run dev` / `npm run build`.
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, "../../out/status.json"); // trading-system/out/status.json
const dest = resolve(here, "../public/status.json");

if (existsSync(src)) {
  mkdirSync(dirname(dest), { recursive: true });
  copyFileSync(src, dest);
  console.log("synced status.json ->", dest);
} else {
  console.warn(
    "no ../../out/status.json yet — run `python scripts/cockpit.py --config h1b` first. Using the bundled sample.",
  );
}
