--!strict
--[[
	Karakter başına durum makinesi:  Idle -> Ready -> Playing <-> Accent / Transition / Recovery -> Outro

	Durumlar ayrık değil AĞIRLIKLIDIR (her durumun yayla yumuşatılmış bir ağırlığı var, toplamı 1):
	geçişte poz atlamaz; katmanlar ctx.sw.* ağırlıklarını okuyup kendi genliklerini karıştırır.
	  Idle       : müzik yok. Nefes, enstrüman gevşek tutuluyor.
	  Ready      : ilk ölçüden önce hazırlık - enstrümanı kaldır, derin nefes, hafif geri yaslan (anticipation).
	  Playing    : ana performans.
	  Accent     : güçlü vuruş (crash, bölüm başı) sonrası ~0.5 sn yoğun tepki.
	  Transition : bölüm sonundaki son ölçü: fill/hazırlık, eğilip geri toplanma.
	  Recovery   : yoğun bölümden sakine geçişte 1 ölçü "nefes verme", omuzlar düşer, hareket azalır.
	  Outro      : final: hareket azalır, son poz tutulur.
]]

local Root = script:FindFirstAncestor("BandPerformance")
local SpringM = require(Root.Util.Spring)
local Spring = SpringM.Spring

local PerformerState = {}

PerformerState.NAMES = { "Idle", "Ready", "Playing", "Accent", "Transition", "Recovery", "Outro" }

function PerformerState.init(perf: any)
	perf.state = "Idle"
	perf.stateEnter = 0
	perf.accentUntil = -1
	perf.accentStrength = 0
	perf.recoveryUntil = -1
	perf.lastSectionIndex = -1
	perf.sw = {}
	for _, n in PerformerState.NAMES do
		perf.sw[n] = Spring.new(n == "Idle" and 1 or 0, 2.4, 1.0)
	end
	perf.swv = {} -- yumuşatılmış, normalize ağırlıklar
	for _, n in PerformerState.NAMES do
		perf.swv[n] = n == "Idle" and 1 or 0
	end
end

-- Güçlü vuruş bildirimi (enstrüman katmanları çağırır)
function PerformerState.accent(perf: any, now: number, strength: number)
	if strength > perf.accentStrength * 0.6 or now > perf.accentUntil then
		perf.accentUntil = now + 0.28 + 0.4 * strength
		perf.accentStrength = strength
	end
end

local function setState(perf: any, name: string, now: number)
	if perf.state ~= name then
		perf.state = name
		perf.stateEnter = now
	end
end

function PerformerState.update(perf: any, ctx: any)
	local now = ctx.time
	local score = perf.score
	local song = score.song
	local sec = ctx.sec
	local prevIdx = perf.lastSectionIndex
	if sec.index ~= prevIdx then
		if prevIdx > 0 then
			local prev = score.sections[prevIdx]
			if prev and sec.intensity < prev.intensity - 0.2 and ctx.bar > 0 then
				perf.recoveryUntil = sec.startT + score.barDur
			end
		end
		perf.lastSectionIndex = sec.index
	end

	local state = perf.state
	local nextState = state
	local inFinalBar = sec.endBar - ctx.bar <= 1 and sec.index < #score.sections
	if not ctx.playing then
		nextState = "Idle"
	elseif sec.kind == "outro" and ctx.bar >= sec.startBar then
		nextState = "Outro"
	elseif state == "Idle" then
		nextState = (now < song.firstBarTime + 0.5) and "Ready" or "Playing"
	elseif state == "Ready" and now - perf.stateEnter > 0.8 and now >= song.firstBarTime - 0.05 then
		nextState = "Playing"
	elseif state == "Ready" then
		nextState = "Ready"
	elseif now < perf.accentUntil then
		nextState = "Accent"
	elseif inFinalBar and ctx.style.fill then
		nextState = "Transition"
	elseif now < perf.recoveryUntil then
		nextState = "Recovery"
	else
		nextState = "Playing"
	end
	setState(perf, nextState, now)

	local sum = 0
	for _, n in PerformerState.NAMES do
		local v = perf.sw[n]:step(n == perf.state and 1 or 0, ctx.dt)
		v = math.max(v, 0)
		perf.swv[n] = v
		sum += v
	end
	if sum < 1e-6 then
		sum = 1
	end
	for _, n in PerformerState.NAMES do
		perf.swv[n] /= sum
	end
	local sw = perf.swv
	ctx.sw = sw
	ctx.state = perf.state
	ctx.playW = sw.Playing + sw.Accent + sw.Transition + 0.85 * sw.Recovery + 0.55 * sw.Outro + 0.4 * sw.Ready
	ctx.contactW = 1 - 0.45 * sw.Idle - 0.1 * sw.Ready
	ctx.groove = ctx.playW * (0.22 + 0.78 * ctx.energy)
end

return PerformerState
