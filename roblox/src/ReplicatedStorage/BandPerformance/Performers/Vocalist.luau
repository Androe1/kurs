--!strict
--[[
	Vokalist (4. karakter) - mimarinin modüler olduğunun kanıtı: yeni bir performer = Performer.new + tek bir
	enstrüman katmanı. Burada "enstrüman" el tipi mikrofon ve serbest sol el jestleridir.

	Vokal hattı sesten ayrıştırılamadı (distorsiyonlu miks) -> fraz yapısı ölçü stilinden (Score.barStyle.vocalOn:
	verse = 3 ölçü şarkı + 1 ölçü nefes, chorus = sürekli) gelir. Gerçek sözler/fraz zamanları biliniyorsa
	Score.barStyles[bar].vocalOn dizisini doldurmak yeterli; animasyon koduna dokunmak gerekmez.

	  * Mikrofon: fraz başlamadan ~0.3 sn ÖNCE ağza kalkar (anticipation + hazırlık nefesi), fraz bitince iner.
	  * Sol el: jestler (göğüs, uzanma, yumruk, dinlenme) yaylı hedefle gelir: hızlı çıkış, aşma, oturma.
	  * Kafa: nakaratta enerjik tepe notalarda geriye atılır, frazlar arasında öne/aşağı rahatlar.
]]

local Root = script:FindFirstAncestor("BandPerformance")
local Config = require(Root.Config)
local SpringM = require(Root.Util.Spring)
local Ease = require(Root.Util.Ease)
local Rng = require(Root.Util.Rng)
local Performer = require(Root.Performers.Performer)
local PerformerState = require(Root.Performers.PerformerState)

local Spring, Spring3 = SpringM.Spring, SpringM.Spring3
local D = Config.deg

local Vocalist = {}
local Layer = {}
Layer.__index = Layer

-- UpperTorso uzayında sol el jest hedefleri: konum + parmak yönü (f) + avuç içi normali (n); X sağ, Y yukarı, Z GERİ (ileri = -Z)
local GESTURES = {
	rest = { pos = Vector3.new(-1.0, -0.75, -0.45), f = Vector3.new(0, -0.9, -0.3), n = Vector3.new(1, 0, 0), w = 0.35 },
	chest = { pos = Vector3.new(-0.30, 0.05, -0.78), f = Vector3.new(0.6, 0.7, -0.2), n = Vector3.new(0, 0, 1), w = 1 },
	reach = { pos = Vector3.new(-1.25, 0.55, -1.45), f = Vector3.new(-0.35, 0.1, -0.93), n = Vector3.new(0, 1, 0), w = 1 },
	pumpUp = { pos = Vector3.new(-0.85, 1.25, -0.95), f = Vector3.new(0, 0.9, -0.4), n = Vector3.new(1, 0, 0.2), w = 1 },
	pumpDown = { pos = Vector3.new(-0.95, 0.15, -0.95), f = Vector3.new(0, 0.9, -0.4), n = Vector3.new(1, 0, 0.2), w = 1 },
	open = { pos = Vector3.new(-1.45, 0.25, -0.85), f = Vector3.new(-0.8, 0.2, -0.5), n = Vector3.new(0.2, 1, 0), w = 1 },
}

-- jest -> UpperTorso uzayında sol el yönelimi (CFrame, dönüş): parmaklar = el -Y, avuç içi = el +X (sol el)
local function gestureRot(g: any): CFrame
	local f = g.f.Unit
	local n = (g.n - f * g.n:Dot(f)).Unit
	return CFrame.fromMatrix(Vector3.zero, n, -f, n:Cross(-f))
end

function Layer.new(perf: any)
	local s = perf.rig.lengths.reach / 2.2
	return setmetatable({
		name = "Vocal",
		s = s,
		micUp = Spring.new(0, 5.0, 0.6),
		gesture = "rest",
		lastGestureBar = -1,
		gestPos = Spring3.new(GESTURES.rest.pos * s, 4.2, 0.5),
		gestW = Spring.new(0.35, 3, 1),
		rotFrom = gestureRot(GESTURES.rest), -- yönelim geçişi: önceki (anlık) yönelim -> yeni jest yönelimi
		rotTo = gestureRot(GESTURES.rest),
		rotCur = gestureRot(GESTURES.rest),
		gestBlend = Spring.new(1, 2.8, 0.7), -- 0 = önceki yönelim, 1 = yeni (aşmalı)
		lastPhraseState = false,
		micWorld = Vector3.zero,
		mouthLook = Spring.new(0, 3, 0.7),
		geo = {},
		micCF = CFrame.identity,
	}, Layer)
end

function Layer.resync(self: any, perf: any, now: number)
	self.lastGestureBar = -1
end

local function pickGesture(perf: any, bar: number, half: number, ctx: any): string
	local kind = ctx.sec.kind
	local h = Rng.hash(perf.seed, bar * 2 + half, 31)
	if kind == "intro" or kind == "outro" then
		return h < 0.7 and "rest" or "chest"
	elseif kind == "calm" then
		return h < 0.4 and "chest" or (h < 0.8 and "rest" or "open")
	elseif kind == "verse" then
		return h < 0.3 and "chest" or (h < 0.55 and "open" or (h < 0.8 and "reach" or "rest"))
	end
	return h < 0.3 and "pumpUp" or (h < 0.55 and "reach" or (h < 0.8 and "open" or "chest"))
end

function Layer.prepare(self: any, perf: any, ctx: any, pose: any)
	local dyn = perf.dyn
	local score = perf.score
	local s = self.s
	local dt = ctx.dt
	local style = ctx.style
	local bar = math.floor(ctx.bar)
	local frac = ctx.bar % 1
	-- fraz durumu: şu anki ölçü ya da (ölçü sonuna yaklaşırken) sonraki ölçü şarkıdaysa mikrofon yukarıda
	local nextStyle = score:barStyle(math.max(bar + 1, 0))
	local phraseNow = style.vocalOn
	local raise = phraseNow or (nextStyle.vocalOn and frac > 0.78)
	if ctx.state == "Idle" or ctx.state == "Outro" then
		raise = false
	end
	self.micUp:step(raise and 1 or 0, dt)

	-- hazırlık nefesi (fraz başlamadan hemen önce) ve fraz sonu soluk verme
	if raise ~= self.lastPhraseState then
		self.lastPhraseState = raise
		local now = ctx.time
		if raise then
			dyn.waist.x:impulseForPeak(-D(3.5))
			dyn.shoulderL:impulseForPeak(Vector3.new(0, 0.06 * s, 0))
			dyn.shoulderR:impulseForPeak(Vector3.new(0, 0.06 * s, 0))
		else
			dyn.waist.x:impulseForPeak(D(3))
			dyn.neck.x:impulseForPeak(D(5))
			dyn.shoulderL:impulseForPeak(Vector3.new(0, -0.05 * s, 0))
			dyn.shoulderR:impulseForPeak(Vector3.new(0, -0.05 * s, 0))
		end
	end

	-- jest seçimi: yarım ölçüde bir
	local half = (frac >= 0.5) and 1 or 0
	local key = bar * 2 + half
	if key ~= self.lastGestureBar and bar >= 0 then
		self.lastGestureBar = key
		self.gesture = pickGesture(perf, bar, half, ctx)
		local g = GESTURES[self.gesture]
		-- hedef değişimi: önce küçük anticipation (zıt yönde), sonra hedef
		self.gestPos.y:impulseForPeak(0.05 * s)
		self.rotFrom = self.rotCur -- anlık yönelimden başla: aşmalı geçişte bile sıçrama yok
		self.rotTo = gestureRot(g)
		self.gestBlend.x = 0
		self.gestBlend.v = 0
	end
	local g = GESTURES[self.gesture]
	-- nakaratta ölçü başı vuruşunda yumruk (pump) darbesi
	for _, b in ctx.beats do
		if b.inBar == 0 and ctx.sec.kind == "chorus" and ctx.groove > 0.4 then
			self.gestPos.y:impulseForPeak(-0.14 * s * ctx.groove)
			perf:at(b.time + 0.03, function()
				dyn.waist.x:impulseForPeak(D(2.5) * ctx.groove)
			end)
		end
	end
	self.gestPos:step(g.pos * s, dt)
	self.gestW:step(g.w, dt)
	self.gestBlend:step(1, dt)

	-- kafa: nakaratta enerjik frazda geriye (yüksek nota), fraz arası öne rahat
	local singing = self.micUp.x
	if ctx.sec.kind == "chorus" and ctx.energy > 0.7 then
		pose.gaze += Vector3.new(-D(9) * singing * math.sin(math.pi * ((ctx.bar % 2) / 2)), 0, 0)
	else
		pose.gaze += Vector3.new(D(3) * singing, 0, 0)
	end
	-- mikrofona doğru hafif eğilme
	perf.bias.waistPitch = D(4) * singing * ctx.playW
	perf.bias.neckYaw = 0
	perf.bias.waistYaw = 0
end

function Layer.contact(self: any, perf: any, ctx: any, pose: any)
	local s = self.s
	local head = ctx.parts.Head
	local ut = ctx.parts.UpperTorso
	local up = self.micUp.x
	-- mikrofon: yukarıda ağız önünde; aşağıda göğüs hizasında sağ yanda
	local mouth = head * Vector3.new(0, -0.18 * s, -0.86 * s)
	local low = ut * Vector3.new(0.55 * s, 0.1 * s, -0.95 * s)
	local micHead = low:Lerp(mouth, Ease.smoothstep(up))
	-- mic ekseni: yukarıda ağıza doğru eğik, aşağıda daha dik
	local axisUp = head:VectorToWorldSpace(Vector3.new(0, 0.62, 0.78).Unit)
	local axisLow = ut:VectorToWorldSpace(Vector3.new(0, 0.9, 0.2).Unit)
	local axis = axisLow:Lerp(axisUp, Ease.smoothstep(up)).Unit
	local hand = micHead - axis * (0.55 * s) -- el, mikrofon başının ~0.55 altında
	-- el yönelimi: parmaklar (-Y) mikrofon eksenine (yukarı), avuç içi mikrofona
	local vy = -axis
	local right = ut:VectorToWorldSpace(Vector3.new(1, 0, 0))
	local vx = (-right - vy * (-right):Dot(vy)).Unit
	local vz = vx:Cross(vy)
	local handRot = CFrame.fromMatrix(Vector3.zero, vx, vy, vz)
	self.micCF = CFrame.lookAt(micHead, micHead + axis * 1.0)
	pose:setHand("Right", {
		cf = CFrame.new(hand) * handRot,
		grip = CFrame.new(0, 0, 0),
		w = ctx.contactW,
		pole = nil,
		elbowOpen = 0.05 * s * up,
	})

	-- sol el: jest
	local gp = self.gestPos:get()
	local wpos = ut * gp
	self.rotCur = self.rotFrom:Lerp(self.rotTo, math.clamp(self.gestBlend.x, 0, 1.2))
	local rot = ut.Rotation * self.rotCur
	pose:setHand("Left", {
		cf = CFrame.new(wpos) * rot,
		grip = CFrame.new(0, -0.2 * s, 0),
		w = ctx.contactW * math.clamp(self.gestW.x, 0, 1),
		pole = nil,
		elbowOpen = 0.04 * s,
	})
end

function Layer.debugGeometry(self: any): { { pts: { Vector3 }, color: string } }
	local c = self.micCF
	return { { color = "#222", pts = { c.Position - c.LookVector * 0.6, c.Position } } }
end

function Vocalist.create(rig: any, opts: { score: any, clock: any, seed: number? })
	return Performer.new(rig, "Vocal", {
		score = opts.score, clock = opts.clock, seed = opts.seed,
		instrument = function(perf)
			return Layer.new(perf)
		end,
	})
end

Vocalist.Layer = Layer

return Vocalist
