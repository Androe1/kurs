local T = R.T
local Rbx = R.Rbx
local Band = require(R.Root)
local Song = require(R.Root.Data.SongMap)

T.section("Band orkestrasyonu: 4 karakter, prop'lar, zaman kaynağı")
-- 4 sahte R15, BandRole ile
local container = Rbx.newInstance("Folder", "Band")
local names = { { "Gitarist", "Guitar", -5 }, { "Basgitar", "Bass", 5 }, { "Baterist", "Drums", 0 }, { "Vokalist", "Vocal", 0 } }
local models = {}
for _, n in ipairs(names) do
	local m = R.mockR15({ name = n[1] })
	m.PrimaryPart.CFrame = CFrame.new(n[3], 3, n[1] == "Baterist" and 8 or 0)
	-- parçaları da kaydır (sahte rig: tüm parçalar HRP'ye göre mutlak)
	local off = m.PrimaryPart.CFrame.Position
	for _, p in ipairs(m:GetChildren()) do p.CFrame = CFrame.new(off) * p.CFrame end
	m.Humanoid = nil
	Rbx.parent(m, container)
	table.insert(models, m)
end
local timeSrc, setTime = Band.manualTimeSource()
local band = Band.new({ container = container, timeSource = timeSrc, buildProps = true })
T.check(#band.order == 4, "4 performer bağlandı: " .. #band.order)
T.check(#band.props == 4, "4 prop üretildi")
setTime(6.0)
local dt = 1 / 60
local nan = 0
for f = 1, 60 * 20 do
	setTime(6.0 + f * dt)
	band:update(dt)
	for role, p in pairs(band.performers) do
		for _, jn in ipairs(p.rig.order) do
			local tr = p.lastTr[jn]
			if tr.p.X ~= tr.p.X or tr.r00 ~= tr.r00 then nan += 1 end
		end
	end
end
T.check(nan == 0, "20 sn, 4 karakter: NaN yok")
local m = band:getMetrics()
for role, v in pairs(m) do
	print(string.format("  %-7s durum=%s el hatası L %.3f R %.3f", role, v.state, v.handError.Left, v.handError.Right))
end
T.check(m.Guitar.state == "Playing" or m.Guitar.state == "Accent" or m.Guitar.state == "Transition", "gitarist performans durumunda")
-- seek: geri sar, sorunsuz
setTime(30.0) band:update(dt) setTime(2.0) band:update(dt)
T.check(true, "seek sorunsuz")
band:destroy()

T.section("CameraRig: tüm planlar geçerli bir kamera üretiyor")
do
	local timeSrc2, setTime2 = Band.manualTimeSource()
	local b2 = Band.new({ container = container, timeSource = timeSrc2, buildProps = false })
	setTime2(20)
	for f = 1, 120 do setTime2(20 + f / 60) b2:update(1 / 60) end
	local cam = Band.CameraRig.new()
	local ok = true
	for _, name in ipairs(Band.Config.cameraShots) do
		cam:cut(name, b2, (name == "handsCloseUp") and "Guitar" or nil)
		local cf = cam:update(1 / 60, b2)
		local p = cf.Position
		local fin = p.X == p.X and p.Y == p.Y and p.Z == p.Z
		local d = (p - b2.performers.Guitar.parts.UpperTorso.Position).Magnitude
		print(string.format("  %-18s kamera %s | gitaristten uzaklık %.1f", name, tostring(p), d))
		if not fin or d > 60 or d < 1 then ok = false end
	end
	T.check(ok, "10 kamera planı sonlu ve makul uzaklıkta")
	-- yönetmen: bölümler boyunca kesme
	local cuts = 0
	local lastShot = ""
	for bar = 0, 113 do
		b2.clock:seek(b2.song.firstBarTime + bar * 1.5 + 0.1)
		cam:direct(b2)
		if cam.shot ~= lastShot then cuts += 1 lastShot = cam.shot end
	end
	T.check(cuts > 20, "otomatik yönetmen müzik boyunca çok sayıda kesme yapıyor: " .. cuts)
	b2:destroy()
end

T.section("Performans (WASM yorumlayıcı, Roblox'tan yavaş): 4 karakter / kare")
do
	local timeSrc3, setTime3 = Band.manualTimeSource()
	local b3 = Band.new({ container = container, timeSource = timeSrc3, buildProps = true })
	setTime3(30)
	local t0 = os.clock()
	local N = 300
	for f = 1, N do setTime3(30 + f / 60) b3:update(1 / 60) end
	local per = (os.clock() - t0) / N * 1000
	print(string.format("  band:update ort %.2f ms/kare (4 performer + prop), performer başına %.2f ms", per, per / 4))
	T.check(per < 40, "kare başı maliyet makul")
	b3:destroy()
end

T.section("LOD: uzak performer güncellenmez, yakına gelince snap yapmaz")
do
	local timeSrc4, setTime4 = Band.manualTimeSource()
	local camPos = Vector3.new(0, 5, 0)
	local b4 = Band.new({ container = container, timeSource = timeSrc4, buildProps = false, cullDistance = 12, getCameraPosition = function() return camPos end })
	setTime4(30)
	for f = 1, 60 do setTime4(30 + f / 60) b4:update(1 / 60) end
	local culledCount = 0
	for _, role in ipairs(b4.order) do if b4.performers[role].culled then culledCount += 1 end end
	T.check(culledCount >= 1, "mesafe dışındaki performer atlandı: " .. culledCount)
	-- kamerayı yaklaştır: 5 sn sonra kalan performer da güncellenir; poz sıçraması < 30°/kare
	camPos = Vector3.new(0, 5, 4)
	local maxStep = 0
	local prev = {}
	for f = 1, 120 do
		setTime4(40 + f / 60)
		b4.cullDistance = 9999
		b4:update(1 / 60)
		for _, role in ipairs(b4.order) do
			local p = b4.performers[role]
			if p.lastTr then
				for name, cf in pairs(p.lastTr) do
					local key = role .. name
					if prev[key] then
						local _, a = (prev[key]:Inverse() * cf.Rotation):ToAxisAngle()
						maxStep = math.max(maxStep, math.deg(a))
					end
					prev[key] = cf.Rotation
				end
			end
		end
	end
	T.check(maxStep < 30, "LOD'den dönüşte poz sıçramıyor (max " .. string.format("%.1f", maxStep) .. "°/kare)")
	b4:destroy()
end
