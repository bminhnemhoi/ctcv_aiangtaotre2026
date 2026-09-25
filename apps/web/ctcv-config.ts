/**
 * Node-side reader for `config/app.yaml` (the single source of UI thresholds, ports and
 * e2e viewports — brief §8). Used by vite.config.ts, the Playwright config and the tests so
 * nothing on the tooling side hard-codes a threshold. Deliberately regex-based (flat keys
 * only) to avoid pulling a YAML parser into the web toolchain.
 */
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));

/** Absolute path of `config/app.yaml` relative to this package. */
export const APP_YAML_PATH = resolve(HERE, '../../config/app.yaml');

export interface Viewport {
  /** Playwright project name, e.g. `360x800`. */
  name: string;
  width: number;
  height: number;
}

export interface AppConfig {
  /** `ui.min_font_pt` — smallest font size allowed anywhere (points). */
  minFontPt: number;
  /** `ui.min_tap_px` — smallest tap target side (CSS px). */
  minTapPx: number;
  /** `ui.viewports` — the phone viewports every e2e run covers. */
  viewports: Viewport[];
  /** `ports.*` — service ports (web dev server, api, ...). */
  ports: Record<string, number>;
}

function readInt(text: string, key: string): number {
  const match = new RegExp(`^\\s*${key}:\\s*(\\d+)\\s*(?:#.*)?$`, 'm').exec(text);
  if (!match) throw new Error(`config/app.yaml: thiếu khóa số nguyên '${key}'`);
  return Number(match[1]);
}

function readBlock(text: string, key: string): string {
  const match = new RegExp(`^${key}:[^\\n]*\\n((?:[ \\t]+[^\\n]*\\n?)+)`, 'm').exec(text);
  if (!match) throw new Error(`config/app.yaml: thiếu khối '${key}'`);
  return match[1] ?? '';
}

function readViewports(text: string): Viewport[] {
  const block = readBlock(readBlock(text, 'ui'), '  viewports');
  const viewports: Viewport[] = [];
  for (const match of block.matchAll(/^\s*-\s*["']?(\d{3,4})x(\d{3,4})["']?\s*$/gm)) {
    const width = Number(match[1]);
    const height = Number(match[2]);
    viewports.push({ name: `${width}x${height}`, width, height });
  }
  if (viewports.length === 0) throw new Error('config/app.yaml: ui.viewports rỗng');
  return viewports;
}

function readPorts(text: string): Record<string, number> {
  const ports: Record<string, number> = {};
  for (const match of readBlock(text, 'ports').matchAll(/^\s+([a-z_]+):\s*(\d+)\s*$/gm)) {
    ports[match[1] ?? ''] = Number(match[2]);
  }
  if (!ports.web || !ports.api) throw new Error('config/app.yaml: ports thiếu web/api');
  return ports;
}

/** Parse the text of `config/app.yaml` into the subset the web toolchain needs. */
export function parseAppYaml(text: string): AppConfig {
  return {
    minFontPt: readInt(text, 'min_font_pt'),
    minTapPx: readInt(text, 'min_tap_px'),
    viewports: readViewports(text),
    ports: readPorts(text),
  };
}

/** Read and parse `config/app.yaml` (or another file, for tests). */
export function readAppConfig(path: string = APP_YAML_PATH): AppConfig {
  return parseAppYaml(readFileSync(path, 'utf8'));
}
