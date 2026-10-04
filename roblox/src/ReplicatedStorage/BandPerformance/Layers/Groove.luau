--!strict
--[[
	İKİNCİL KATMAN (secondary): ritme bağlı gövde tepkisi + ağırlık transferi + kafa.

	Kinetik zincir:  vuruş -> kalça çökmesi -> belden (waist) öne eğilme -> kafa selamı -> omuz çökmesi
	Her halka AYRI bir yay ve bir sonrakine milisaniyelik gecikmeyle itilir; hedef pozlara tween yok.
	Ağırlık transferi: önce zıt yöne küçük bir anticipation, sonra kalça kayması, göğüs karşı rotasyonu,
	kafa dengeyi korur (counter-rotation), sonra oturma (settle). Rastgelelik yalnızca Rng ile deterministik.
]]

local Root = script:FindFirstAncestor("BandPerformance")
local Config = require(Root.Config)
local Rng = require(Root.Util.Rng)
local PoseM = require(Root.Layers.Pose)

local Groove = {}
Groove.__index = Groove

local BEAT_STRENGTH = { 1.0, 0.55, 0.8, 0.55 }
local D = Config.deg

function Groove.new(perf: any)
	return setmetatable({
		name = "Groove",
		shiftSign = 1,
		shiftTarget = 0,
		lastPeriod = -1,
	}, Groove)
end

function Groove.resync(self: any, perf: any, now: number)
	self.lastPeriod = -1
end

local function chain(perf: any, now: number, d: number, fn: () -> ())
	if d <= 0.001 then
		fn()
	else
		perf:at(now + d, fn)
	end
end

function Groove.prepare(self: any, perf: any, ctx: any, pose: any)
	local P = perf.profile
	local dyn = perf.dyn
	local g = ctx.groove
	local style = ctx.style
	local dt = ctx.dt
	local lim = Config.limits
	local headAmp = style.headAmp

	-- ── ritim: her vuruşta kinetik zincir
	for _, b in ctx.beats do
		local str = BEAT_STRENGTH[b.inBar + 1] * g
		if b.inBar == 0 then
			str *= style.accentBoost
		end
		-- sakin bas sustain'inde (kısa bölümlerde) hareket yumuşar
		local t = b.time
		local bd = P.bounceDelay
		if P.bounce > 0 then
			chain(perf, t, bd, function()
				dyn.pelvisY:impulseForPeak(-P.bounce * str)
			end)
		end
		chain(perf, t, bd + 0.025, function()
			dyn.waist.x:impulseForPeak(P.nod * 0.45 * str)
		end)
		chain(perf, t, bd + 0.05, function()
			dyn.neck.x:impulseForPeak(P.nod * str * headAmp)
		end)
		chain(perf, t, bd + 0.03, function()
			dyn.shoulderL:impulseForPeak(Vector3.new(0, -0.05 * str, 0))
			dyn.shoulderR:impulseForPeak(Vector3.new(0, -0.05 * str, 0))
		end)
		-- hafif yanal/yaw sallanma: ölçü başı vuruşunda omuz-kalça ters yaw (karşıt rotasyon)
		if b.inBar == 0 or b.inBar == 2 then
			local s = (b.inBar == 0 and 1 or -1) * style.swayDir
			chain(perf, t, bd + 0.02, function()
				dyn.waist.y:impulseForPeak(s * D(2.2) * g)
				dyn.pelvisRot.y:impulseForPeak(-s * D(1.4) * g)
			end)
			chain(perf, t, bd + 0.07, function()
				dyn.neck.y:impulseForPeak(s * D(3) * g * headAmp * P.headLead * 2)
			end)
		end
	end

	-- ── ağırlık transferi (her weightPeriodBars ölçüde): anticipation -> kayma -> göğüs karşıt -> oturma
	local period = math.floor(ctx.bar / P.weightPeriodBars)
	if period ~= self.lastPeriod and ctx.bar >= 0 then
		local first = self.lastPeriod < 0
		self.lastPeriod = period
		if first then
			self.shiftSign = (Rng.hash(perf.seed, period, 1) < 0.5) and 1 or -1
		else
			self.shiftSign = -self.shiftSign
			local change = self.shiftSign
			local nowT = ctx.time
			-- anticipation: yeni yönün tersine küçük hamle (yaklaşık 120 ms önce kalkıyor olurdu; burada hemen)
			dyn.pelvisShift.x:impulseForPeak(-change * P.sway * 0.18)
			dyn.waist.z:impulseForPeak(change * D(1.2))
		end
	end
	local amp = P.sway * (0.35 + 0.65 * g)
	-- stance değişimi (varyasyon: döngü 4, ilk ölçü): daha büyük kayma, ayak yeniden dengelenir
	if style.stanceShift then
		amp *= 1.45
	end
	local shiftTarget = self.shiftSign * amp
	local sx = dyn.pelvisShift.x:step(shiftTarget, dt)
	dyn.pelvisShift.z:step(0, dt)
	-- kalça düşüşü yüksüz taraf, göğüs/baş karşıt
	local rollTarget = self.shiftSign * D(3.2) * (0.3 + 0.7 * g) -- ağırlık sağ ayakta: sağ kalça yukarı, sol düşer
	local pr = dyn.pelvisRot:step(Vector3.new(P.lean * -0.15 * g, 0, rollTarget), dt)
	-- göğüs: karşı rotasyon (pelvis roll'ın -c katı), yaylı -> gecikme + overshoot
	local bias = perf.bias
	local waistTarget = Vector3.new(P.lean * 0.4 * g + bias.waistPitch, bias.waistYaw, -pr.Z * P.chestCounter)
	local w = dyn.waist:step(waistTarget, dt)
	-- kafa: gövde sallanmasını dengeler (gözler yatay kalır), performans yönüne hafif önde gider
	local neckTarget = Vector3.new(
		-(w.X + pr.X) * 0.45 + pose.gaze.X,
		-w.Y * 0.35 + P.headLead * ctx.style.swayDir * D(4) * g + pose.gaze.Y + bias.neckYaw,
		-(pr.Z + w.Z) * 0.8
	)
	local nk = dyn.neck:step(neckTarget, dt)
	local sL = dyn.shoulderL:step(Vector3.zero, dt)
	local sR = dyn.shoulderR:step(Vector3.zero, dt)

	-- ── pelvis -> pose
	local py = dyn.pelvisY:step(0, dt)
	pose:addRoot(Vector3.new(sx, py, dyn.pelvisShift.z.x), PoseM.angles(Vector3.new(pr.X, pr.Y, math.clamp(pr.Z, -lim.rootRoll, lim.rootRoll))))
	pose:addEuler("Waist", Vector3.new(math.clamp(w.X, -lim.waistPitch, lim.waistPitch), math.clamp(w.Y, -lim.waistYaw, lim.waistYaw), math.clamp(w.Z, -lim.waistRoll, lim.waistRoll)))
	pose:addEuler("Neck", Vector3.new(math.clamp(nk.X, -lim.neckPitch, lim.neckPitch), math.clamp(nk.Y, -lim.neckYaw, lim.neckYaw), math.clamp(nk.Z, -lim.neckRoll, lim.neckRoll)))
	pose:addShoulder("Left", sL)
	pose:addShoulder("Right", sR)
end

return Groove
