local T = R.T
local Song = require(R.Root.Data.SongMap)
local Score = require(R.Root.Music.Score)
local Clock = require(R.Root.Music.Clock)
local R15Rig = require(R.Root.Rig.R15Rig)
local Performer = require(R.Root.Performers.Performer)

T.section("Gövde katmanları (enstrümansız): kararlılık, ayak planı, eklem aralıkları")
local score = Score.build(Song, 3)
local clock = Clock.new(Song, 0)
local model = R.mockR15({ name = "Test" })
local rig = R15Rig.new(model)
local perf = Performer.new(rig, "Guitar", { score = score, clock = clock })

local dt = 1 / 60
local maxAnkleDrift = 0
local minY, maxY = 1e9, -1e9
local bad = 0
local jumps = 0
local prevPelvis
local maxStep = 0
local ankleRest = { Right = perf.rest.ankle.Right, Left = perf.rest.ankle.Left }
clock:seek(0)
for frame = 1, 60 * 40 do
	clock:update(dt, nil, true)
	perf:update(dt)
	local parts = perf.parts
	-- NaN kontrolü
	for _, name in ipairs(rig.order) do
		local t = perf.lastTr[name]
		if t.p.X ~= t.p.X or t.r00 ~= t.r00 then bad += 1 end
	end
	for _, side in ipairs({ "Right", "Left" }) do
		local j = rig.joints[side .. "Ankle"]
		local a = (parts[j.part0] * j.c0).Position
		-- hedef ayak planına ne kadar yakın (yük kayması hariç lift/genişlik: yatay sapma)
		local tgt = perf.pose.feet[side]
		maxAnkleDrift = math.max(maxAnkleDrift, (a - tgt.ankle).Magnitude)
	end
	local pel = parts.LowerTorso.Position
	if prevPelvis then maxStep = math.max(maxStep, (pel - prevPelvis).Magnitude) end
	prevPelvis = pel
	minY, maxY = math.min(minY, pel.Y), math.max(maxY, pel.Y)
end
T.check(bad == 0, "40 sn boyunca NaN yok")
T.check(maxAnkleDrift < 0.02, "ayaklar planlı konumda kalıyor, max sapma " .. string.format("%.4f", maxAnkleDrift))
print(string.format("  pelvis dikey aralığı: %.3f .. %.3f, kare başı max adım %.4f", minY, maxY, maxStep))
T.check(maxY - minY > 0.03 and maxY - minY < 0.6, "kalça hareketi makul (yaşayan ama abartısız)")
T.check(maxStep < 0.06, "kalça kare başına sıçramıyor")
local m = perf.metrics
print(string.format("  duruma: %s, enerji %.2f", perf.state, perf.ctx.energy))
