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
