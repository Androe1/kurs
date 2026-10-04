local T = R.T
local Rbx = R.Rbx
local Song = require(R.Root.Data.SongMap)
local Score = require(R.Root.Music.Score)
local Clock = require(R.Root.Music.Clock)
local Strum = require(R.Root.Layers.Strum)
local R15Rig = require(R.Root.Rig.R15Rig)

local FACT = {
	Guitar = require(R.Root.Performers.Guitarist),
	Bass = require(R.Root.Performers.Bassist),
	Drums = require(R.Root.Performers.Drummer),
	Vocal = require(R.Root.Performers.Vocalist),
}
local score = Score.build(Song, 3)

local function percentile(t, p)
	local c = table.clone(t)
	table.sort(c)
	return c[math.max(1, math.min(#c, math.floor(#c * p)))] or 0
end

local function run(role, fps, t0, t1, hook)
	local clock = Clock.new(Song, 0)
	local rig = R15Rig.new(R.mockR15({ name = role }))
	local perf = FACT[role].create(rig, { score = score, clock = clock })
	local dt = 1 / fps
	clock:seek(t0)
	local frame = 0
	while clock.rawTime < t1 do
		clock:update(dt, nil, true)
		perf:update(dt)
		frame += 1
		hook(perf, frame, dt)
	end
	return perf
end

T.section("Strum eğrisi: geçiş anı = ses anı, yön doğru")
do
	local bad, n = 0, 0
	local maxS = 0
	for i = 5, #score.guitar - 5 do
		local e = score.guitar[i]
		local s, ds = Strum.eval(score.guitar, e.t + 1e-6)
		n += 1
		maxS = math.max(maxS, math.abs(s))
		if ds * e.dir <= 0 then bad += 1 end
	end
	T.check(maxS < 1e-3, "her vuruş anında konum ip düzleminde (max |s| " .. string.format("%.5f", maxS) .. ")")
	T.check(bad == 0, "vuruş yönü eğrinin hız yönüyle uyumlu")
	-- süreklilik
	local maxJump = 0
	local prev
	for t = 12, 40, 1 / 240 do
		local s = Strum.eval(score.guitar, t)
		if prev then maxJump = math.max(maxJump, math.abs(s - prev)) end
		prev = s
	end
	T.check(maxJump < 0.12, "strum konumu sürekli (max Δs/4ms " .. string.format("%.3f", maxJump) .. ")")
end

for _, role in ipairs({ "Guitar", "Bass", "Drums", "Vocal" }) do
	T.section("Hareket denetimi: " .. role .. " (tüm şarkı, 60 fps)")
	local prevRot = {}
	local maxDeg, deg99 = 0, {}
	local maxElbow, maxKnee = 0, 0
	local minElbow = 1e9
	local reachBad, frames = 0, 0
	local handErrMax = 0
	local prevHead, prevHead2
	local accs = {}
	local cycFeat = {}
	local states = {}
	local lastState
	local footDrift = 0
	local worstJoint = ""
	local perf = run(role, 60, 0, 172, function(perf, frame, dt)
		frames += 1
		local tr = perf.lastTr
		for name, cf in pairs(tr) do
			local ax, ang = cf:ToAxisAngle()
			local pr = prevRot[name]
			if pr then
				local rel = pr:Inverse() * cf
				local _, a = rel:ToAxisAngle()
				local d = math.deg(a)
				table.insert(deg99, d)
				if d > maxDeg then maxDeg = d worstJoint = name end
			end
			prevRot[name] = cf.Rotation
		end
		for _, side in ipairs({ "Right", "Left" }) do
			local _, ea = tr[side .. "Elbow"]:ToAxisAngle()
			maxElbow = math.max(maxElbow, math.deg(ea))
			minElbow = math.min(minElbow, math.deg(ea))
			local _, ka = tr[side .. "Knee"]:ToAxisAngle()
			maxKnee = math.max(maxKnee, math.deg(ka))
			if perf.metrics.reach[side] > 0.05 then reachBad += 1 end
			handErrMax = math.max(handErrMax, perf.metrics.handError[side])
		end
		-- baş ivmesi
		local hp = perf.parts.Head.Position
		if prevHead and prevHead2 then
			local a = (hp - 2 * prevHead + prevHead2).Magnitude / (dt * dt)
			table.insert(accs, a)
		end
		prevHead2, prevHead = prevHead, hp
		-- durumlar
		if perf.state ~= lastState then table.insert(states, string.format("%.1f:%s", perf.clock.time, perf.state)) lastState = perf.state end
		-- varyasyon: chorus 52-108, 4 ölçülük döngü başına istatistik
		local bar = perf.clock.bar
		if bar >= 52 and bar < 108 then
			local cyc = math.floor((bar - 52) / 4)
			local f = { math.abs(perf.dyn.waist.y.x), math.abs(perf.dyn.neck.x.x), math.abs(perf.dyn.pelvisShift.x.x), math.abs(perf.dyn.pelvisY.x), math.abs(perf.dyn.waist.x.x) }
			cycFeat[cyc] = cycFeat[cyc] or { 0, 0, 0, 0, 0, n = 0 }
			for i = 1, 5 do cycFeat[cyc][i] += f[i] end
			cycFeat[cyc].n += 1
		end
	end)
	local function mean(t) local s = 0 for _, v in ipairs(t) do s += v end return s / math.max(#t, 1) end
	print(string.format("  eklem hızı (°/kare): p99.9 %.2f, max %.2f (%s)", percentile(deg99, 0.999), maxDeg, worstJoint))
	print(string.format("  dirsek %.0f°..%.0f°, diz max %.0f°; erişilemeyen kare %%%.2f; max el hatası %.3f", minElbow, maxElbow, maxKnee, 100 * reachBad / (frames * 2), handErrMax))
	local accP = percentile(accs, 0.5)
	print(string.format("  kafa ivmesi (stud/s²): medyan %.1f, p99 %.1f, max %.1f", accP, percentile(accs, 0.99), percentile(accs, 1)))
	print("  durumlar: " .. table.concat(states, " "):sub(1, 150))
	-- döngü çeşitliliği: ardışık 4 ölçülük döngülerin özellik vektörleri (gövde yaw, baş, kayma, bounce, eğilme) arası ort. bağıl uzaklık
	local dists = {}
	local prevV
	for c = 0, 13 do
		local f = cycFeat[c]
		if f then
			local v = {}
			for i = 1, 5 do v[i] = f[i] / math.max(f.n, 1) end
			if prevV then
				local num, den = 0, 0
				for i = 1, 5 do num += (v[i] - prevV[i]) ^ 2 den += (v[i] ^ 2 + prevV[i] ^ 2) / 2 end
				table.insert(dists, math.sqrt(num / math.max(den, 1e-12)))
			end
			prevV = v
		end
	end
	local variation = mean(dists)
	print(string.format("  döngü varyasyonu (ardışık 4 ölçülük döngüler arası bağıl uzaklık): %.3f", variation))
	T.check(maxElbow < 155, role .. ": dirsek hiperfleksiyon yok")
	T.check(minElbow > -1, role .. ": dirsek hiperekstansiyon yok")
	T.check(maxKnee < 145, role .. ": diz sınırı içinde")
	T.check(maxDeg < 28, role .. ": hiçbir eklem tek karede >28° dönmüyor (snap yok), max " .. string.format("%.1f", maxDeg) .. " " .. worstJoint)
	T.check(reachBad / (frames * 2) < 0.02, role .. ": kareslerin >%98'inde hedefe erişildi")
	T.check(handErrMax < 0.2, role .. ": el temas hatası < 0.2 stud")
	T.check(variation > 0.08, role .. ": ardışık döngüler birbirinin kopyası değil (varyasyon " .. string.format("%.3f", variation) .. ")")
end

T.section("Kare hızından bağımsızlık (30 fps vs 60 fps)")
for _, role in ipairs({ "Guitar", "Drums" }) do
	local function final(fps)
		local out
		run(role, fps, 40, 50, function(perf) out = perf.parts end)
		return out
	end
	local a, b = final(60), final(30)
	local worst = 0
	for _, jn in ipairs({ "Head", "RightHand", "LeftHand", "LowerTorso" }) do
		worst = math.max(worst, (a[jn].Position - b[jn].Position).Magnitude)
	end
	print(string.format("  %s: 60 vs 30 fps aynı müzik anında max konum farkı %.3f stud", role, worst))
	T.check(worst < 0.35, role .. ": kare hızı sonucu bozmuyor")
end

T.section("Durum geçişleri: Idle -> Ready -> Playing -> Outro snap yapmıyor")
for _, role in ipairs({ "Guitar", "Bass", "Drums", "Vocal" }) do
	local clock = Clock.new(Song, 0)
	local rig = R15Rig.new(R.mockR15({ name = role }))
	local perf = FACT[role].create(rig, { score = score, clock = clock })
	local dt = 1 / 60
	local prevRot = {}
	local maxDeg, worst = 0, ""
	local seen = {}
	local function step(playing, t)
		clock:update(dt, t, playing)
		perf:update(dt)
		seen[perf.state] = true
		for name, cf in pairs(perf.lastTr) do
			local pr = prevRot[name]
			if pr then
				local _, a = (pr:Inverse() * cf.Rotation):ToAxisAngle()
				if math.deg(a) > maxDeg then maxDeg = math.deg(a) worst = name end
			end
			prevRot[name] = cf.Rotation
		end
	end
	-- 1.5 sn müzik yok (Idle), sonra çalmaya başla (şarkı başı), sonra bitişe atla (outro) ve dur
	for i = 1, 90 do step(false, nil) end
	local idleState = perf.state
	for i = 1, 60 * 6 do step(true, nil) end
	local mid = perf.state
	clock:seek(160)
	for i = 1, 60 * 14 do step(true, nil) end
	for i = 1, 90 do step(false, nil) end
	local endState = perf.state
	print(string.format("  %-7s Idle->...: %s | görülen durumlar: %s | max eklem Δ %.1f°/kare (%s)", role, idleState .. "/" .. mid .. "/" .. endState, (function() local t = {} for k in pairs(seen) do table.insert(t, k) end table.sort(t) return table.concat(t, ",") end)(), maxDeg, worst))
	T.check(idleState == "Idle" and endState == "Idle", role .. ": müzik durunca Idle'a döner")
	T.check(seen.Ready and seen.Playing and seen.Outro, role .. ": Ready/Playing/Outro durumları ziyaret edildi")
	T.check(maxDeg < 30, role .. ": durum geçişlerinde snap yok (max " .. string.format("%.1f", maxDeg) .. "°/kare)")
end
