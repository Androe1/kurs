local T = R.T
local Song = require(R.Root.Data.SongMap)
local Score = require(R.Root.Music.Score)
local Clock = require(R.Root.Music.Clock)

T.section("SongMap + Score")
T.near(Song.bpm, 160, 0.01, "tempo 160")
T.check(Song.bars == 114, "114 ölçü")
local sc = Score.build(Song, 7)
print("  bölümler:")
for _, s in sc.sections do print(string.format("    %d. ölçü %3d-%3d  %-6s yoğunluk %.2f", s.index, s.startBar, s.endBar, s.kind, s.intensity)) end
print(string.format("  davul olayı %d, gitar vuruşu %d, akor değişimi %d, bas notası %d", #sc.drums, #sc.guitar, #sc.chords, #sc.bass))
T.check(#sc.drums > 800 and #sc.drums < 6000, "makul davul olayı sayısı")
-- sıralı mı
for _, name in ipairs({ "drums", "guitar", "chords", "bass" }) do
	local ok = true
	for i = 2, #sc[name] do if sc[name][i].t < sc[name][i - 1].t then ok = false end end
	T.check(ok, name .. " zamana göre sıralı")
end
-- 6.4 sn büyük vuruşta kick + snare + crash var mı (ölçü 4, slot 0)
local t4 = Song.firstBarTime + 4 * (240 / Song.bpm)
local found = {}
for _, e in ipairs(Score.eventsIn(sc.drums, t4 - 0.01, t4 + 0.01)) do found[e.kind] = true end
T.check(found.kick, "ölçü 4 vuruş 1'de kick")
T.check(found.crash, "ölçü 4 vuruş 1'de crash (bölüm başı)")
-- akorlar Eb Cm Gm Bb: pc 3,0,7,10
local pcs = {}
for i = 1, 8 do table.insert(pcs, sc.chords[i].pc) end
print("  ilk akor kökleri (pc): " .. table.concat(pcs, ","))
T.check(sc.chords[1].pc == 3 and sc.chords[2].pc == 0, "Eb -> Cm ilerlemesi")
local frets = {}
for i = 1, 8 do table.insert(frets, sc.chords[i].fret) end
print("  gitar perdeleri: " .. table.concat(frets, ","))
-- gitar vuruş yönleri dönüşümlü
local up, down = 0, 0
for _, e in ipairs(sc.guitar) do if e.dir == 1 then down += 1 else up += 1 end end
T.check(down > 100 and up > 100, "aşağı/yukarı vuruş dengeli: " .. down .. "/" .. up)
local ghost, mute = 0, 0
for _, e in ipairs(sc.guitar) do if e.kind == "ghost" then ghost += 1 elseif e.kind == "mute" then mute += 1 end end
print(string.format("  hayalet vuruş %d, muted %d", ghost, mute))
-- bas: tel/perde makul
local maxFret, strings = 0, {}
for _, e in ipairs(sc.bass) do maxFret = math.max(maxFret, e.fret) strings[e.string] = true end
T.check(maxFret <= 12, "bas perdeleri <= 12")
print("  bas: ilk 6 nota: " .. (function() local t = {} for i = 1, 6 do local e = sc.bass[i] table.insert(t, string.format("%d(t%d/f%d)", e.midi, e.string, e.fret)) end return table.concat(t, " ") end)())
-- Clock
local clk = Clock.new(Song, 0)
clk:update(0.016, 6.5, true)
T.near(clk.bar, (6.5 - Song.firstBarTime) / 1.5, 1e-6, "ölçü hesabı")
T.check(clk.beatFloat >= 0 and clk.beatFloat < 4, "vuruş aralığı")
-- drift düzeltme: ölçüm 50 ms ileri sıçrarsa saat yumuşakça yakalar
local c2 = Clock.new(Song, 0)
c2:update(0.016, 10, true)
local t0 = c2.rawTime
c2:update(0.016, 10.066, true)
T.check(c2.rawTime < 10.066 and c2.rawTime > t0, "küçük sapma yumuşak düzeltiliyor")
