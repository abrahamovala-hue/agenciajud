/**
 * Testes mínimos do schema/validador do VideoEditSpec.
 *
 * Infraestrutura deliberadamente simples: sem framework de teste (Jest/
 * Vitest) — só `node:assert` e o próprio Node executando TypeScript
 * nativamente (Node 22+). Roda com: `npm test`.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import {
  parseVideoEditSpec,
  VideoEditSpecValidationError,
} from "../src/schema/video-edit-spec.schema.ts";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const sampleReelPath = path.join(__dirname, "..", "examples", "sample-reel.json");

const loadSample = (): unknown => JSON.parse(readFileSync(sampleReelPath, "utf-8"));

const deepClone = <T,>(value: T): T => JSON.parse(JSON.stringify(value));

let passed = 0;
let failed = 0;

function expectValid(name: string, data: unknown): void {
  try {
    parseVideoEditSpec(data);
    console.log(`PASS  ${name}`);
    passed += 1;
  } catch (error) {
    console.error(`FAIL  ${name} — esperava validar, mas lancou:`, error);
    failed += 1;
  }
}

function expectInvalid(name: string, data: unknown, expectedFragment: string): void {
  try {
    parseVideoEditSpec(data);
    console.error(`FAIL  ${name} — esperava erro, mas validou sem lancar.`);
    failed += 1;
  } catch (error) {
    const isValidationError = error instanceof VideoEditSpecValidationError;
    const message = error instanceof Error ? error.message : String(error);
    if (isValidationError && message.includes(expectedFragment)) {
      console.log(`PASS  ${name}`);
      passed += 1;
    } else {
      console.error(
        `FAIL  ${name} — erro nao continha "${expectedFragment}" ou nao era VideoEditSpecValidationError:`,
        message,
      );
      failed += 1;
    }
  }
}

// A. sample-reel válido -> passa
expectValid("A. sample-reel.json valido", loadSample());

// B. assetId inexistente -> falha
const withBadAssetId = deepClone(loadSample()) as { timeline: { assetId: string }[] };
withBadAssetId.timeline[0].assetId = "does-not-exist";
expectInvalid("B. assetId inexistente", withBadAssetId, "assetId");

// C. end menor (ou igual) que start -> falha
const withBadRange = deepClone(loadSample()) as { timeline: { start: number; end: number }[] };
withBadRange.timeline[0].end = withBadRange.timeline[0].start;
expectInvalid("C. end <= start", withBadRange, "end deve ser maior que start");

// D. fps inválido -> falha
const withBadFps = deepClone(loadSample()) as { project: { fps: number } };
withBadFps.project.fps = 0;
expectInvalid("D. fps invalido (0)", withBadFps, "fps");

// E. campo obrigatório ausente -> falha
const withMissingField = deepClone(loadSample()) as { project: Record<string, unknown> };
delete withMissingField.project.width;
expectInvalid("E. campo obrigatorio ausente (project.width)", withMissingField, "width");

console.log(`\n${passed} passaram, ${failed} falharam.`);
if (failed > 0) {
  process.exit(1);
}
