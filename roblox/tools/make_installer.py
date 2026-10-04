#!/usr/bin/env python3
"""Studio Command Bar'a yapıştırılacak TEK dosyalık kurulum scripti üretir (Rojo gerekmez)."""
import os, sys
root = os.path.join(os.path.dirname(__file__), '..', 'src')
out = sys.argv[1] if len(sys.argv) > 1 else 'BandInstaller.lua'

def lit(src):
    n = 3
    while ']' + '=' * n + ']' in src:
        n += 1
    eq = '=' * n
    return f'[{eq}[\n{src}]{eq}]'

items = []  # (path tuple, class, source)
base = os.path.join(root, 'ReplicatedStorage', 'BandPerformance')
for d, _, fs in os.walk(base):
    for f in sorted(fs):
        if not f.endswith('.luau'): continue
        rel = os.path.relpath(os.path.join(d, f), base).replace(os.sep, '/')
        parts = rel[:-5].split('/')
        if parts == ['init']: parts = []
        items.append((parts, open(os.path.join(d, f), encoding='utf8').read()))
items.sort(key=lambda x: len(x[0]))
L = ['-- Band Performance kurulumu: Studio > View > Command Bar\'a yapıştır, Enter.',
     'local RS, SSS, SPS = game:GetService("ReplicatedStorage"), game:GetService("ServerScriptService"), game:GetService("StarterPlayer").StarterPlayerScripts',
     'for _, p in {RS:FindFirstChild("BandPerformance"), SSS:FindFirstChild("BandServer"), SPS:FindFirstChild("BandClient")} do p:Destroy() end',
     'local function mk(parent, cls, name, src) local i = Instance.new(cls) i.Name = name if src then i.Source = src end i.Parent = parent return i end',
     'local root']
for parts, src in items:
    if not parts:
        L.append(f'root = mk(RS, "ModuleScript", "BandPerformance", {lit(src)})')
folders = set()
for parts, src in items:
    if not parts: continue
    parent = 'root'
    for i, f in enumerate(parts[:-1]):
        key = tuple(parts[:i+1])
        v = 'F_' + '_'.join(key)
        if key not in folders:
            L.append(f'local {v} = mk({parent}, "Folder", "{f}")')
            folders.add(key)
        parent = v
    L.append(f'mk({parent}, "ModuleScript", "{parts[-1]}", {lit(src)})')
srv = open(os.path.join(root, 'ServerScriptService', 'BandServer.server.luau'), encoding='utf8').read()
cli = open(os.path.join(root, 'StarterPlayer', 'StarterPlayerScripts', 'BandClient.client.luau'), encoding='utf8').read()
L.append(f'mk(SSS, "Script", "BandServer", {lit(srv)})')
L.append(f'mk(SPS, "LocalScript", "BandClient", {lit(cli)})')
L.append('print("BandPerformance kuruldu. workspace.Band klasörüne karakterleri koy, BandRecord = true yap, Play.")')
open(out, 'w', encoding='utf8').write('\n'.join(L) + '\n')
print(out, os.path.getsize(out) // 1024, 'KB')
