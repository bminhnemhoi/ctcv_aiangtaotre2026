import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
export const REPO_ROOT = resolve(HERE, '../../../..');
const DEFAULT_OUT = 'docs/dossier/out/dfl/video';

/** Demo output folder: `CTCV_DEMO_OUT` (relative to the repo root) or the v1 default. */
export function demoOutDir(): string {
  return resolve(REPO_ROOT, process.env.CTCV_DEMO_OUT?.trim() || DEFAULT_OUT);
}
