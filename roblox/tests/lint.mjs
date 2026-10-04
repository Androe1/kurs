// Luau statik analizi (lint + nonstrict tip denetimi). Roblox globalleri `globals` ile bildirilir.
import { Analysis } from '@luau-rs/luau/analysis';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const srcRoot = path.join(here, '..', 'src');
function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => e.isDirectory() ? walk(path.join(dir, e.name)) : [path.join(dir, e.name)]);
}
const files = walk(srcRoot).filter((f) => f.endsWith('.luau') && !f.includes('SongMap'));
const robloxGlobals = ['Vector3', 'CFrame', 'Instance', 'Enum', 'Color3', 'game', 'workspace', 'script', 'task', 'typeof', 'warn', 'time', 'tick', 'os', 'bit32', 'require', 'Random'];
const analysis = await Analysis.create({ mode: process.env.MODE || 'nonstrict', lint: true, globals: robloxGlobals });
let errors = 0, warnings = 0;
const SKIP = new Set(['LocalShadow', 'FunctionUnused', 'ImportUnused', 'LocalUnused', 'DeprecatedGlobal']);
for (const f of files) {
  const rel = path.relative(srcRoot, f);
  analysis.setModule(rel, fs.readFileSync(f, 'utf8'));
}
for (const f of files) {
  const rel = path.relative(srcRoot, f);
  const r = await analysis.check(rel);
  for (const d of r.diagnostics) {
    const code = String(d.code);
    if (d.severity === 'warning' && /(LocalUnused|FunctionUnused|ImportUnused|LocalShadow|UnusedLocal|ShadowedLocal)/i.test(code + d.message)) continue;
    if (/Unused|shadow/i.test(d.message)) continue;
    if (d.severity === 'error') errors++; else warnings++;
    console.log(`${rel}:${d.location.begin.line + 1}:${d.location.begin.column + 1} [${d.severity}] ${code} ${d.message}`);
  }
}
console.log(`\n${files.length} dosya, ${errors} hata, ${warnings} uyarı`);
process.exit(0);
