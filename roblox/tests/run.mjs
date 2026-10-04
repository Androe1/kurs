// Luau VM (WASM) içinde BandPerformance çekirdeğini ve testleri çalıştırır.
//   node roblox/tests/run.mjs [testAdı ...]      (npm i @luau-rs/luau gerekir)
import { Lua } from '@luau-rs/luau';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const srcRoot = path.join(here, '..', 'src', 'ReplicatedStorage', 'BandPerformance');
const only = process.argv.slice(2);

function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? walk(path.join(dir, e.name)) : [path.join(dir, e.name)]);
}

const modules = []; // {id, parentId, name, class, code}
const dirIds = new Map();
let nextId = 1;
function ensureDir(rel) {
  if (rel === '') return 'root';
  if (dirIds.has(rel)) return dirIds.get(rel);
  const parts = rel.split('/');
  const name = parts.pop();
  const parent = ensureDir(parts.join('/'));
  const id = 'd' + nextId++;
  dirIds.set(rel, id);
  modules.push({ id, parentId: parent, name, cls: 'Folder', code: null });
  return id;
}
// kök: init.luau -> BandPerformance modülü
modules.push({ id: 'root', parentId: null, name: 'BandPerformance', cls: 'ModuleScript',
  code: fs.readFileSync(path.join(srcRoot, 'init.luau'), 'utf8') });
for (const f of walk(srcRoot).sort()) {
  const rel = path.relative(srcRoot, f).replaceAll('\\', '/');
  if (rel === 'init.luau' || !rel.endsWith('.luau')) continue;
  const dir = path.dirname(rel) === '.' ? '' : path.dirname(rel);
  modules.push({ id: 'm' + nextId++, parentId: ensureDir(dir), name: path.basename(rel, '.luau'), cls: 'ModuleScript',
    code: fs.readFileSync(f, 'utf8') });
}
const mockRbx = fs.readFileSync(path.join(here, 'mock', 'Rbx.luau'), 'utf8');
const testFiles = fs.readdirSync(here).filter((f) => f.endsWith('.test.luau')).sort()
  .filter((f) => only.length === 0 || only.some((o) => f.startsWith(o)));

const envPairs = Object.entries(process.env).filter(([k]) => /^(ROLE|T0|T1|STEP|SEED|SCENE)$/.test(k)).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(', ');
const lineMap = [];
let bundle = '';
function emit(text, label) {
  lineMap.push({ start: bundle.split('\n').length, label });
  bundle += text;
}
emit(`
local __log = {}
function print(...) local t = {} for i = 1, select('#', ...) do t[i] = tostring((select(i, ...))) end table.insert(__log, table.concat(t, " ")) end
local __Rbx = (function()
`, 'prelude');
emit(mockRbx.replace(/^--!.*$/m, ''), 'mock/Rbx.luau');
emit(`
end)()
Vector3, CFrame = __Rbx.Vector3, __Rbx.CFrame
Instance = { new = function(cls) return __Rbx.newInstance(cls, cls) end }
Color3 = { fromRGB = function(r, g, b) return { r, g, b } end }
Enum = setmetatable({}, { __index = function(t, k) local v = setmetatable({}, { __index = function(_, n) return k .. "." .. n end }) rawset(t, k, v) return v end })
local __nodes, __defs, __cache, __ids = {}, {}, {}, {}
`, 'prelude2');
for (const m of modules) {
  emit(`__nodes["${m.id}"] = __Rbx.newInstance("${m.cls}", "${m.name}")\n`, 'node');
}
for (const m of modules) {
  if (m.parentId) emit(`__Rbx.parent(__nodes["${m.id}"], __nodes["${m.parentId}"])\n`, 'node');
}
emit(`
function require(node)
  local def = __defs[node]
  if def == nil then error("require: modül değil: " .. tostring(node and node.Name)) end
  local c = __cache[node]
  if c == nil then c = { v = def(node) } __cache[node] = c end
  return c.v
end
`, 'require');
for (const m of modules.filter((x) => x.code !== null)) {
  emit(`__defs[__nodes["${m.id}"]] = function(script)\n`, 'wrap');
  emit(m.code.replace(/^export type/gm, 'type').replace(/^--!.*$/gm, ''), `src/${m.name}`);
  emit(`\nend\n`, 'wrap');
}
emit(`
local Root = __nodes["root"]
local T = { passed = 0, failed = 0 }
function T.check(cond, msg) if cond then T.passed += 1 else T.failed += 1 print("  ✗ BAŞARISIZ: " .. msg) end end
function T.near(a, b, tol, msg) T.check(math.abs(a - b) <= tol, string.format("%s (beklenen %.4f, bulunan %.4f, tol %.4f)", msg, b, a, tol)) end
function T.section(name) print("▸ " .. name) end
local R = { Rbx = __Rbx, Root = Root, T = T, nodes = __nodes, env = { ${envPairs} } }
R.mockR15 = (function(...)
`, 'harness');
emit(fs.readFileSync(path.join(here, 'mock', 'R15Mock.luau'), 'utf8').replace(/^--!.*$/m, ''), 'mock/R15Mock.luau');
emit(`
end)(__Rbx)
`, 'harness2');
for (const tf of testFiles) {
  const code = fs.readFileSync(path.join(here, tf), 'utf8').replace(/^--!.*$/gm, '');
  emit(`do\nlocal ok, err = xpcall(function(R)\n`, 'testwrap');
  emit(code, tf);
  emit(`\nend, function(e) return debug.traceback(tostring(e), 2) end, R)\nif not ok then T.failed += 1 print("  ✗ HATA (${tf}): " .. tostring(err)) end\nend\n`, 'testwrap');
}
emit(`print(string.format("\\n%d kontrol geçti, %d başarısız", T.passed, T.failed))\nreturn table.concat(__log, "\\n")\n`, 'tail');

fs.writeFileSync(path.join(here, '.bundle.luau'), bundle);
const lua = await Lua.create({ sandbox: false });
let out;
try {
  out = lua.execute(bundle);
} catch (e) {
  let msg = String(e.message ?? e);
  const m = msg.match(/rs:\d+:(\d+)/) || msg.match(/:(\d+):/);
  if (m) {
    const ln = +m[1];
    const seg = [...lineMap].reverse().find((s) => s.start <= ln);
    if (seg) msg += `\n   -> ${seg.label}, satır ${ln - seg.start + 1}`;
  }
  console.error(msg);
  process.exit(2);
}
if (process.env.LOG_FILE) fs.writeFileSync(process.env.LOG_FILE, out[0]);
console.log(process.env.LOG_FILE ? out[0].split('\n').filter((l) => !l.startsWith('DUMP ')).join('\n') : out[0]);
process.exit(/ 0 başarısız/.test(out[0]) ? 0 : 1);
