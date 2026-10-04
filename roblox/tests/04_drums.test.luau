local T = R.T
local Song = require(R.Root.Data.SongMap)
local Score = require(R.Root.Music.Score)
local Clock = require(R.Root.Music.Clock)
local R15Rig = require(R.Root.Rig.R15Rig)
local Drummer = require(R.Root.Performers.Drummer)

T.section("Davulcu: çubuk ucu vuruş anında davula değiyor mu, anatomi, kick pedalı")
local score = Score.build(Song, 3)
local clock = Clock.new(Song, 0)
local rig = R15Rig.new(R.mockR15({ name = "Drummer" }))
local perf = Drummer.create(rig, { score = score, clock = clock })
local layer = perf.instrument
local dt = 1 / 60

-- reach analizi: her davul için bilek hedefinin omuza uzaklığı / erişim (stick ucundan geri)
local lay = layer.layout
local s = layer.s
local order = { "snare", "tom1", "tom2", "floor", "hat", "crash", "ride" }
local shoulder = { Right = rig.joints.RightShoulder, Left = rig.joints.LeftShoulder }
local seated = Vector3.new(0, -lay.seatDrop, 0)
for _, nm in ipairs(order) do
	local pc = lay.pieces[nm]
	local out = {}
	for _, side in ipairs({ "Right", "Left" }) do
		local sh = (rig.rootCF * rig.joints.Root.c0 * rig.joints.Waist.c0).Position + seated -- yaklaşık: omuz = UT merkezinde yan
		local ut = rig.rootCF * rig.joints.Waist.c0 * rig.joints.Waist.c0
		local shoulderPos = (rig.rootCF * rig.joints.Waist.c0 * rig.joints.RightShoulder.c0).Position
		local sx = side == "Right" and 1.5 or -1.5
		shoulderPos = Vector3.new(sx, 1.6, 0) + seated
		local dirH = Vector3.new(pc.pos.X - shoulderPos.X, 0, pc.pos.Z - shoulderPos.Z).Unit
		local d = Vector3.new(dirH.X * math.cos(math.rad(-8)), math.sin(math.rad(-8)), dirH.Z * math.cos(math.rad(-8)))
		local grip = pc.pos - d * (layer.stickLen - layer.gripAt)
		local dist = (grip - shoulderPos).Magnitude
		table.insert(out, string.format("%s %.2f", side, dist / rig.lengths.reach))
	end
	print(string.format("  erişim oranı (el-omuz/erişim) %-6s %s", nm, table.concat(out, " | ")))
end

-- simülasyon: vuruş anlarında ucun yüzeye mesafesi
local errs = { snare = {}, hat = {}, crash = {}, tom = {}, ride = {} }
local ext = {} -- drum -> {el-omuz mesafesi/erişim}
local maxErr, sumErr, n = 0, 0, 0
local worstKind = ""
local maxElbow, maxKnee = 0, 0
local minElbow = 1e9
local pelvisMin, pelvisMax = 1e9, -1e9
local hitList = {}
for _, side in ipairs({ "Right", "Left" }) do for _, e in ipairs(layer.hits[side]) do table.insert(hitList, { e = e, side = side }) end end
table.sort(hitList, function(a, b) return a.e.t < b.e.t end)
local hi = 1
local T0, T1 = 6.0, 40.0
clock:seek(T0 - 1)
local handsAbovePlane = 0
while clock.rawTime < T1 do
	clock:update(dt, nil, true)
	perf:update(dt)
	local parts = perf.parts
	-- eklem açıları: dirsek fleksiyonu
	for _, side in ipairs({ "Right", "Left" }) do
		local tr = perf.lastTr[side .. "Elbow"]
		local ax, ang = tr:ToAxisAngle()
		maxElbow = math.max(maxElbow, math.deg(ang))
		minElbow = math.min(minElbow, math.deg(ang))
		local k = perf.lastTr[side .. "Knee"]
		local _, kang = k:ToAxisAngle()
		maxKnee = math.max(maxKnee, math.deg(kang))
	end
	pelvisMin = math.min(pelvisMin, parts.LowerTorso.Position.Y)
	pelvisMax = math.max(pelvisMax, parts.LowerTorso.Position.Y)
	-- ilk vuruş zamanı bu karede geçildiyse ucun gerçek konumunu ölç
	while hitList[hi] and hitList[hi].e.t <= clock.time do
		local h = hitList[hi]
		hi += 1
		if h.e.t > T0 then
			-- olay anına en yakın kare: şimdiki kare (dt/2 hata payı)
			local handCF = parts[h.side .. "Hand"]
			local dirActual = handCF:VectorToWorldSpace(Vector3.new(0, -1, 0))
			local tipActual = handCF.Position + dirActual * (layer.stickLen - layer.gripAt)
			-- yüzeyle mesafe: kare içi zaman farkı yüzünden hedefe hızla yaklaşıyor; yatay + düşey ayrı
			local err = (tipActual - h.e.hit).Magnitude
			maxErr = math.max(maxErr, err)
			sumErr += err n += 1
			local shJ = rig.joints[h.side .. "Shoulder"]
			local wrJ = rig.joints[h.side .. "Wrist"]
			local shP = (parts[shJ.part0] * shJ.c0).Position
			local wrP = (parts[wrJ.part0] * wrJ.c0).Position
			local key = h.e.drum .. "/" .. h.side
			ext[key] = ext[key] or {}
			table.insert(ext[key], (wrP - shP).Magnitude / rig.lengths.reach)
			local list = errs[h.e.kind == "hatOpen" and "hat" or h.e.kind]
			if list then table.insert(list, err) end
		end
	end
end
local function mean(t) local s = 0 for _, v in ipairs(t) do s += v end return #t > 0 and s / #t or 0 end
print(string.format("  vuruş sayısı %d, çubuk ucu hatası ort %.3f maks %.3f stud (kare aralığı: hız*1/120 sn payı dahil)", n, sumErr / math.max(n, 1), maxErr))
for k, t in pairs(errs) do print(string.format("    %-6s n=%d ort %.3f", k, #t, mean(t))) end
local keys = {}
for k in pairs(ext) do table.insert(keys, k) end
table.sort(keys)
for _, k in ipairs(keys) do local t = ext[k] local mn, mx = 9, 0 for _, v in ipairs(t) do mn = math.min(mn, v) mx = math.max(mx, v) end print(string.format("    kol uzanımı %-12s n=%2d ort %.2f [%.2f..%.2f]", k, #t, mean(t), mn, mx)) end
print(string.format("  dirsek açısı aralığı %.0f° .. %.0f°, diz max %.0f°, kalça yüksekliği %.2f .. %.2f", minElbow, maxElbow, maxKnee, pelvisMin, pelvisMax))
T.check(n > 100, "yeterli vuruş ölçüldü")
T.check(sumErr / math.max(n, 1) < 0.12, "çubuk ucu vuruşta yüzeye ortalama < 0.12 stud")
T.check(maxElbow < 155, "dirsek hiperfleksiyon yok")
T.check(minElbow >= -1, "dirsek hiperekstansiyon yok (açı >= 0)")
T.check(maxKnee < 145, "diz sınırı")
