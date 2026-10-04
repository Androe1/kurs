--!strict
--[[
	Telli enstrüman katmanı (gitar ve bas aynı iskeleti paylaşır, KARAKTERİ farklıdır):
	  * enstrüman gövdeye (UpperTorso) askıyla bağlı rijit çerçeve + follow-through yayı
	  * SOL EL: perde istasyonunda boyun üzerinde; akor/nota değişiminde anticipation -> kayma (el kalkar) -> oturma
	  * SAĞ EL: gitar = strum (bilek ana kaynak, dirsek yardımcı), bas = parmak pluck (el sakin, parmak dalışı)
	  * vuruş olayları kinetik zincire dönüşür: bilek -> dirsek -> omuz -> göğüs -> kalça -> kafa (gecikmeli darbeler)
	Tüm uzunluklar rig'in erişimine (reach) göre ölçeklenir; referans erişim 2.2 stud.

	Enstrüman çerçevesi G (yerel): +X = başlığa (headstock), +Z = akustik yüzeyin dışı (teller o tarafta),
	+Y = üst kenar (tiz olmayan, kalın tel tarafı).
]]

local Root = script:FindFirstAncestor("BandPerformance")
local Config = require(Root.Config)
local SpringM = require(Root.Util.Spring)
local Ease = require(Root.Util.Ease)
local Score = require(Root.Music.Score)
local Strum = require(Root.Layers.Strum)
local Follow = require(Root.Layers.Follow)
local PerformerState = require(Root.Performers.PerformerState)

local Spring, Spring3 = SpringM.Spring, SpringM.Spring3
local D = Config.deg

local Stringed = {}
Stringed.__index = Stringed

--[[ Spec'ler (referans erişim 2.2 stud için; s ile ölçeklenir). Birim: stud. ]]
Stringed.SPECS = {
	Guitar = {
		mode = "strum",
		strapPos = Vector3.new(0.55, -0.55, -0.62), -- UpperTorso uzayında gövde merkezi
		neckDir = Vector3.new(-0.90, 0.33, -0.28), -- UpperTorso uzayında boyun yönü (sol, yukarı, öne)
		nutX = 2.15, scaleLen = 2.6, neckHalfWidth = 0.11,
		strum = Vector3.new(0.30, 0.0, 0.16), -- G uzayında pena/parmak temas noktası
		strumAxisY = 0.28, -- vuruş genliği (stud)
		lagFreq = 3.6, lagDamp = 0.42,
	},
	Bass = {
		mode = "pluck",
		strapPos = Vector3.new(0.50, -0.80, -0.62),
		neckDir = Vector3.new(-0.84, 0.30, -0.45),
		nutX = 2.55, scaleLen = 3.1, neckHalfWidth = 0.16,
		strum = Vector3.new(0.52, 0.0, 0.16),
		strumAxisY = 0.12,
		lagFreq = 3.0, lagDamp = 0.5, -- bas daha ağır
	},
}

local function fretX(spec: any, fret: number, s: number): number
	return (spec.nutX - spec.scaleLen * (1 - 2 ^ (-fret / 12))) * s
end

-- UpperTorso uzayından G çerçevesinin taban CFrame'i
local function strapFrame(spec: any, s: number): CFrame
	local x = spec.neckDir.Unit
	local zHint = Vector3.new(0, 0, -1)
	local z = (zHint - x * zHint:Dot(x)).Unit
	local y = z:Cross(x)
	return CFrame.fromMatrix(spec.strapPos * s, x, y, z)
end

function Stringed.new(perf: any, specName: string)
	local spec = Stringed.SPECS[specName]
	local s = perf.rig.lengths.reach / 2.2
	local self = setmetatable({
		name = specName,
		spec = spec,
		s = s,
		strap = strapFrame(spec, s),
		follow = Follow.new(spec.lagFreq, spec.lagDamp, 0.8, 0.5),
		fret = Spring.new(5, 5.5, 0.62), -- sol el istasyonu (perde)
		fretString = Spring.new(0, 6, 0.8),
		press = Spring.new(0, 9, 0.5),
		handR = Spring3.new(Vector3.zero, 6, 0.5), -- sağ el takip yayı (G uzayı, vuruş yönünde aşma)
		elbowOpen = Spring.new(0, 4.5, 0.6),
		pluck = Spring.new(0, 14, 0.45),
		pluckSide = Spring.new(0, 10, 0.6),
		lastFret = 5,
		lastFretT = -1,
		G = CFrame.identity,
		geo = {},
		lastStrokeT = -1,
	}, Stringed)
	return self
end

function Stringed.resync(self: any, perf: any, now: number)
	self.follow:reset()
end

-- ───── FAZ 1: olaylar -> kinetik zincir darbeleri, bakış, perde hedefi ─────
function Stringed.prepare(self: any, perf: any, ctx: any, pose: any)
	local score = perf.score
	local dyn = perf.dyn
	local now = ctx.time
	local dt = ctx.dt
	local P = perf.profile
	local g = ctx.groove
	local isBass = self.spec.mode == "pluck"

	-- ── sol el hedef perdesi (öngörü: değişimden ~0.1 sn önce harekete başla)
	local lead = isBass and 0.07 or 0.11
	local fretTarget = self.lastFret
	if isBass then
		local list = score.bass
		local i = Score.firstIndexAtOrAfter(list, now + lead + 1e-9) - 1
		local e = list[i]
		if e and now + lead < e.t + e.dur + 0.6 then
			fretTarget = e.fret
			self.fretString:step(e.string, dt)
			self.stringTarget = e.string
		end
	else
		local list = score.chords
		local i = Score.firstIndexAtOrAfter(list, now + lead + 1e-9) - 1
		local e = list[i]
		if e then
			fretTarget = e.fret
			self.stringTarget = e.string
		end
	end
	local prevFret = self.fret.x
	self.fret:step(fretTarget, dt)
	local fretVel = self.fret.v
	self.lastFret = fretTarget
	self.fretSpeed = math.abs(fretVel)

	-- ── bakış: perde değişirken boyuna bak (aşağı), sonra kitleye dön
	local lookDown = math.clamp((self.fretSpeed - 1.2) / 5, 0, 1)
	pose.gaze += Vector3.new(D(11) * lookDown * ctx.playW, -D(5) * lookDown * ctx.playW, 0)

	-- ── sustain: son nota/boşluktan beri uzun süre vuruş yoksa (bas) gövde ve el sakinleşir
	if isBass then
		local e = score.bass[math.max(Score.firstIndexAtOrAfter(score.bass, now + 1e-9) - 1, 1)]
		local since = e and (now - e.t) or 0
		perf.calmTarget = (since > 0.42) and 1 or 0
	else
		perf.calmTarget = 0
	end

	-- ── vuruş olayları
	if isBass then
		self:_basePluckEvents(perf, ctx)
	else
		self:_strumEvents(perf, ctx)
	end

	-- ── cümle bazlı eğilme (öne/geriye): 4 ölçülük cümlede yoğunluk tırmanır, sonda geriye toplanır
	local phase = (ctx.bar % 4) / 4
	local lean = math.sin(phase * math.pi) -- cümle ortasında en öne
	local waistPitch = P.lean * (0.35 * lean * g - 0.25 * (1 - lean) * g)
	if ctx.style.hold then
		waistPitch += -D(2.5) * Ease.smoothstep((phase - 0.7) / 0.3) -- cümle sonu: pose hold, geriye yaslan
	end
	pose:addEuler("Waist", Vector3.new(waistPitch, 0, 0), ctx.playW)
end

function Stringed._strumEvents(self: any, perf: any, ctx: any)
	local dyn = perf.dyn
	local P = perf.profile
	local strums = perf.score.guitar
	for _, e in perf:take("guitar", strums, ctx.time) do
		local str = e.str
		if e.kind == "ghost" then
			str *= 0.25
		end
		local k = str * ctx.groove * ctx.style.accentBoost
		local t = e.t
		local d = e.dir
		-- bilek zaten eğriyle hareket ediyor; zincirin geri kalanı vuruşa tepki verir (gecikmeli, çok küçük)
		perf:at(t, function()
			self.handR:impulseForPeak(Vector3.new(0, -d * 0.045 * k, 0.02 * k)) -- el aşar (follow-through)
			self.elbowOpen:impulseForPeak(0.035 * k) -- dirsek hafif açılır
		end)
		perf:at(t + 0.018, function()
			dyn.shoulderR:impulseForPeak(Vector3.new(0.01 * k, -d * 0.03 * k, -0.015 * k))
		end)
		perf:at(t + 0.035, function()
			dyn.waist.x:impulseForPeak(-d * D(0.9) * k) -- göğüs karşı tepki (counter-motion)
			dyn.waist.y:impulseForPeak(d * D(0.7) * k)
		end)
		perf:at(t + 0.05, function()
			dyn.pelvisShift.x:impulseForPeak(d * 0.012 * k) -- çok küçük ağırlık transferi
		end)
		perf:at(t + 0.065, function()
			dyn.neck.x:impulseForPeak(D(1.6) * k * ctx.style.headAmp) -- kafa ritme mikro
		end)
		-- gitar kendine çekilir: aşağı vuruşta gövdeye doğru
		if e.kind == "accent" or e.kind == "down" then
			perf:at(t, function()
				self.follow:kick(Vector3.new(0, 0, 0.03 * k), Vector3.new(0, 0, d * D(1.0) * k))
			end)
		end
		if e.kind == "accent" and e.str >= 0.9 then
			PerformerState.accent(perf, t, math.min(1, e.str * ctx.groove + 0.1))
			perf:at(t + 0.02, function()
				dyn.pelvisY:impulseForPeak(-0.035 * k)
				self.press:impulseForPeak(0.02)
			end)
		end
	end
end

function Stringed._basePluckEvents(self: any, perf: any, ctx: any)
	local dyn = perf.dyn
	local P = perf.profile
	for _, e in perf:take("bass", perf.score.bass, ctx.time) do
		local k = e.str * ctx.groove
		local t = e.t
		local side = e.finger == 1 and 1 or -1
		perf:at(t, function()
			self.pluck:impulseForPeak(0.05 * e.str) -- parmak teli çeker: el hafifçe dalar ve geri döner
			self.pluckSide:impulseForPeak(side * 0.02)
		end)
		-- güçlü nota: kalça + gövde + omuz vurgusu (düşük frekans hissi)
		if e.str >= 0.7 then
			perf:at(t + 0.01, function()
				dyn.pelvisY:impulseForPeak(-P.bounce * 1.2 * k)
				dyn.pelvisRot.z:impulseForPeak(side * D(1.4) * k)
			end)
			perf:at(t + 0.035, function()
				dyn.waist.x:impulseForPeak(D(1.5) * k)
				dyn.waist.z:impulseForPeak(-side * D(1.1) * k)
				dyn.shoulderR:impulseForPeak(Vector3.new(0, -0.035 * k, 0))
				dyn.shoulderL:impulseForPeak(Vector3.new(0, -0.02 * k, 0))
			end)
			perf:at(t + 0.06, function()
				dyn.neck.x:impulseForPeak(D(2.4) * k * ctx.style.headAmp)
			end)
			perf:at(t, function()
				self.follow:kick(Vector3.new(0, 0, 0.025 * k), Vector3.new(0, 0, -D(0.8) * k))
			end)
		end
		if e.str >= 0.9 then
			PerformerState.accent(perf, t, math.min(1, k + 0.1))
		end
	end
end

-- ───── FAZ 2: enstrüman çerçevesi ve el hedefleri ─────
function Stringed.contact(self: any, perf: any, ctx: any, pose: any)
	local spec, s = self.spec, self.s
	local dt = ctx.dt
	local ut = ctx.parts.UpperTorso
	local isBass = spec.mode == "pluck"

	-- enstrüman çerçevesi: askıya bağlı + follow-through
	local offset = self.follow:step(ut, dt)
	local G = ut * self.strap * offset
	self.G = G

	-- ── SOL EL: perde istasyonu
	local f = self.fret.x
	local fv = self.fretSpeed or 0
	local lift = math.clamp(fv * 0.012, 0, 0.14) * s -- kayarken el boyundan hafifçe kalkar
	local stringT = self.stringTarget or 5
	local yStr = 0.0
	if isBass then
		yStr = (3 - (self.fretString.x - 1)) / 4 * 0.0 -- bas: tel konumu (aşağıda)
		yStr = ((3.0 - self.fretString.x) / 2.0) * spec.neckHalfWidth * 0.8
	else
		yStr = spec.neckHalfWidth * 0.55 * ((stringT == 6) and 1 or 0.55)
	end
	local press = self.press.x
	local tip = Vector3.new(fretX(spec, f, s) - 0.045 * s, yStr * s, (0.14 + lift - press) * s)
	local leftRot = CFrame.fromMatrix(Vector3.zero, Vector3.new(0, 1, 0), Vector3.new(0, 0, -1), Vector3.new(-1, 0, 0)) -- el X=+Y_G, Y=-Z_G (parmaklar +Z), Z=-X_G
	-- parmak ucu çerçevesi
	pose:setHand("Left", {
		cf = G * CFrame.new(tip) * leftRot,
		grip = CFrame.new(0, -0.30 * s, 0),
		w = ctx.contactW,
		pole = nil,
		elbowOpen = 0,
	})

	-- ── SAĞ EL
	local base = spec.strum * s
	-- sağ el yönelimi (G uzayı): parmaklar (el -Y) = f = (0,-0.5,-0.87): tellere dik + yüzey boyunca aşağı.
	local fV = Vector3.new(0, -0.5, -0.87)
	local rightRot0 = CFrame.fromMatrix(Vector3.zero, Vector3.new(0, -0.87, 0.5), Vector3.new(0, 0.5, 0.87), Vector3.new(-1, 0, 0))
	local handOff = self.handR:get()
	local eo = self.elbowOpen.x
	local tipR: Vector3
	local rotR = rightRot0
	if not isBass then
		local sPos, sVel, a, b, u = Strum.eval(perf.score.guitar, ctx.time)
		local A = spec.strumAxisY * s
		-- bilek ana kaynak: ucu bilek etrafında yay çizer; dirsek yardımcı: bilek pivotu da vuruş yönünde 1/4 kayar
		local wristLen = 0.30 * s
		local theta = -sPos * D(24) -- bilek fleksiyonu (+s = aşağı vuruş: uç tiz tellere, -Y_G)
		local pivot = base - fV * wristLen + Vector3.new(0, -sPos * A * 0.28, 0) -- dirsek yardımı: pivot 1/4 oranında kayar
		local rot = CFrame.Angles(theta, 0, 0)
		tipR = pivot + rot:VectorToWorldSpace(fV * wristLen) + handOff
		rotR = rot * rightRot0
		-- iplerden uzaklaşırken el hafifçe kalkar; vuruş anında ip düzleminde
		tipR += Vector3.new(0, 0, math.abs(sPos) * 0.05 * s)
		self.strokeS = sPos
	else
		-- bas: el pickup bölgesinde sakin; tel değişince hafif yana, pluck'ta dalış
		local yBand = ((3.0 - self.fretString.x) / 2.0) * spec.neckHalfWidth * 1.2
		tipR = base + Vector3.new(self.pluckSide.x * s, yBand * s * 0.8, 0.12 * s - self.pluck.x * s) + handOff
		self.strokeS = 0
	end
	pose:setHand("Right", {
		cf = G * CFrame.new(tipR) * rotR,
		grip = CFrame.new(0, -0.30 * s, 0),
		w = ctx.contactW,
		pole = nil,
		elbowOpen = eo,
	})
	self.handR:step(Vector3.zero, dt)
	self.elbowOpen:step(0, dt)
	self.pluck:step(0, dt)
	self.pluckSide:step(0, dt)
	self.press:step(0, dt)
end

-- Önizleme (test/preview) için telli çalgının tel çerçevesi: dünya uzayında çoklu çizgiler
function Stringed.debugGeometry(self: any): { { pts: { Vector3 }, color: string } }
	local spec, s, G = self.spec, self.s, self.G
	local isBass = spec.mode == "pluck"
	local bodyL, bodyW = (isBass and 0.95 or 0.85) * s, (isBass and 0.62 or 0.58) * s
	local thick = 0.15 * s
	local nut = spec.nutX * s
	local hw = spec.neckHalfWidth * s
	local function w(x: number, y: number, z: number): Vector3
		return G * Vector3.new(x, y, z)
	end
	local geo = {}
	-- gövde (üst yüz ve alt yüz dikdörtgeni)
	for _, z in { thick, -thick } do
		table.insert(geo, { color = "#c0392b", pts = { w(-bodyL, -bodyW, z), w(bodyL, -bodyW, z), w(bodyL, bodyW, z), w(-bodyL, bodyW, z), w(-bodyL, -bodyW, z) } })
	end
	-- boyun + başlık
	table.insert(geo, { color = "#8e5a2b", pts = { w(bodyL, -hw, 0.03 * s), w(nut, -hw, 0.03 * s), w(nut, hw, 0.03 * s), w(bodyL, hw, 0.03 * s) } })
	table.insert(geo, { color = "#8e5a2b", pts = { w(nut, -hw, 0.03 * s), w(nut + 0.45 * s, -hw * 1.2, 0.03 * s), w(nut + 0.45 * s, hw * 1.2, 0.03 * s), w(nut, hw, 0.03 * s) } })
	-- teller
	local nStr = isBass and 4 or 6
	for i = 1, nStr do
		local y = hw * (1 - 2 * (i - 0.5) / nStr) * 0.9
		table.insert(geo, { color = "#ddd", pts = { w(-0.5 * s, y * 0.5, thick + 0.01 * s), w(nut, y, 0.045 * s) } })
	end
	-- perde konumu işareti (sol el istasyonu)
	table.insert(geo, { color = "#2ecc71", pts = { w(fretX(spec, self.fret.x, s), -hw, 0.06 * s), w(fretX(spec, self.fret.x, s), hw, 0.06 * s) } })
	return geo
end

return Stringed
