--!strict
--[[
	Davulcu. En çok BODY MECHANICS isteyen karakter:
	  * Oturuş: kalça tabureye alçalır (Root.Transform), baldır dik, kalça sabit ama vuruşta çok küçük tepki verir.
	  * Çubuk ucu YOLU: iki vuruş arasında asimetrik yay (hızlı geri tepme, ağır ivmelenen düşüş). Vuruş anında
	    uç tam davul yüzeyinde. Çubuk eğimi bilekte değişir; büyük vuruşta dirsek/omuz da devreye girer (IK).
	  * Ayaklar: sağ = kick pedalı (ayak pedalı takip eder: topuk kalkar, ayak ucu basar), sol = hi-hat pedalı
	    (2. ve 4. vuruşta chick, open hat'te kalkar). Ayakların görevi farklı.
	  * Gövde: vurulan davula doğru dönüş (tom fill'de set boyunca yön değiştirir), crash'te büyük kinetik zincir
	    (kol -> omuz -> üst gövde -> kafa -> kalça), hi-hat'te küçük/hızlı tepki.
]]

local Root = script:FindFirstAncestor("BandPerformance")
local Config = require(Root.Config)
local SpringM = require(Root.Util.Spring)
local Ease = require(Root.Util.Ease)
local Score = require(Root.Music.Score)
local Performer = require(Root.Performers.Performer)
local PerformerState = require(Root.Performers.PerformerState)
local DrumKit = require(Root.Performers.DrumKit)

local Spring, Spring3 = SpringM.Spring, SpringM.Spring3
local D = Config.deg

local Drummer = {}
local DrumLayer = {}
DrumLayer.__index = DrumLayer

local HAND_KINDS = { snare = true, tom = true, hat = true, hatOpen = true, crash = true, ride = true }

function DrumLayer.new(perf: any)
	local rig = perf.rig
	local layout = DrumKit.layout(rig, rig.rootCF)
	local s = layout.scale
	local self = setmetatable({
		name = "Drums",
		layout = layout,
		s = s,
		hits = { Right = {}, Left = {} } :: { [string]: { any } },
		kicks = {} :: { any },
		hatFoot = {} :: { any },
		stickLen = 1.35 * s,
		gripAt = 0.30 * s, -- tutuş noktasının kıç ucundan uzaklığı
		tipState = {},
		sticks = { Right = { tip = Vector3.zero, grip = Vector3.zero, dir = Vector3.new(0, 0, -1) }, Left = { tip = Vector3.zero, grip = Vector3.zero, dir = Vector3.new(0, 0, -1) } },
		footPitch = { Right = 0, Left = 0 },
		pedalLift = { Right = 0, Left = 0 },
		lateral = Spring.new(0, 3.0, 0.8),
		geo = {},
	}, DrumLayer)
	perf.seated = true
	self:_index(perf)
	-- dinlenme el konumları: omuzdan öne, snare/hi-hat üstünde
	self.restTip = {
		Right = self.layout.pieces.snare.pos + Vector3.new(0.22 * s, 0.35 * s, 0),
		Left = self.layout.pieces.snare.pos + Vector3.new(-0.22 * s, 0.35 * s, 0),
	}
	return self
end

function DrumLayer._hitPoint(self: any, e: any, side: string): Vector3
	local piece = self.layout.pieces[e.drum == "hatOpen" and "hat" or e.drum]
	if e.drum == "kick" then
		return piece.pos
	end
	-- vuruş noktası: elin tarafına ofsetli (iki el aynı noktaya çarpmasın), crash/ride vurgusu kenara
	local sgn = side == "Right" and 1 or -1
	local right = Vector3.new(1, 0, 0)
	local off = right * (sgn * 0.2 * piece.radius)
	local toward = Vector3.new(0, 0, 1) * (0.25 * piece.radius)
	if e.kind == "crash" then
		off = right * (-0.1 * piece.radius) + Vector3.new(0, 0, 1) * (0.55 * piece.radius)
	elseif e.kind == "ride" then
		off = right * (sgn * 0.1 * piece.radius) + Vector3.new(0, 0, 1) * (0.2 * piece.radius)
	elseif piece.kind == "hat" then
		off = Vector3.new(0, 0, 1) * (0.25 * piece.radius)
	end
	local p = piece.pos + off
	-- yüzeye izdüşüm (eğik düzlem)
	local n = piece.normal
	local d = (p - piece.pos):Dot(n)
	p -= n * d
	return p + n * (piece.thickness * 0.5) * (piece.kind == "head" and 1 or 0.2)
end

function DrumLayer._index(self: any, perf: any)
	for _, e in perf.score.drums do
		if e.kind == "kick" then
			table.insert(self.kicks, e)
		elseif HAND_KINDS[e.kind] and e.hand then
			e.hit = self:_hitPoint(e, e.hand)
			table.insert(self.hits[e.hand], e)
		end
	end
	for _, e in perf.score.drums do
		-- hi-hat ayağı: 2. ve 4. vuruş (slot%16 == 4, 12) chick + open hat'te kalkma
		if e.slot % 16 == 4 or e.slot % 16 == 12 or e.kind == "hatOpen" then
			if e.kind == "snare" or e.kind == "hatOpen" then
				table.insert(self.hatFoot, e)
			end
		end
	end
end

-- Asimetrik vuruş yayı: iki vuruş arası yükseklik h(t) ∈ [0, A]. Vuruşta (u=0 ve u=1) h=0, anlık hız ≠ 0 (geri tepme/çarpma).
local function arc(tRel: number, T: number, A: number, riseT: number, fallT: number): number
	if tRel < 0 or tRel > T then
		return 0
	end
	if tRel < riseT then
		local w = tRel / riseT
		return A * (2 * w - w * w) -- hızlı geri tepme, tepede yavaşlar
	end
	if tRel > T - fallT then
		local v = (tRel - (T - fallT)) / fallT
		return A * (1 - v * v) -- tepeden hızlanarak düşer (yerçekimi gibi), çarpmada hız sürer
	end
	return A
end

-- elin (side) t anındaki çubuk ucu: konum, yön, yükseklik (0..), bilgi
function DrumLayer.sampleHand(self: any, side: string, now: number)
	local list = self.hits[side]
	local s = self.s
	local i = Score.firstIndexAtOrAfter(list, now + 1e-9) - 1
	local a, b = list[i], list[i + 1]
	local restTip = self.restTip[side]
	local tipA = a and a.hit or restTip
	local tipB = b and b.hit or tipA
	local T: number
	local tRel: number
	local Aboost = 1
	if a and b then
		T = b.t - a.t
		tRel = now - a.t
	elseif b then
		-- ilk vuruştan önce: el dinlenme noktasında, vuruştan 0.6 sn önce hazırlık yayına başlar
		T = 0.6
		tRel = now - (b.t - T)
		tipA = restTip
	elseif a then
		-- son vuruştan sonra: geri tepme ile kalkar ve el havada bekler (hiçbir zaman ani düşüş yok)
		T = 1e9
		tRel = now - a.t
		tipB = restTip
	else
		T, tRel = 1e9, 0
	end
	-- genlik: iki vuruş arası süre ve sonraki vuruşun gücü; büyük vuruşa hazırlık (anticipation) daha yüksek kalkar
	local strB = b and b.str or 0.4
	local kindB = b and b.kind or "snare"
	local Aneed = s * (0.10 + 0.5 * math.min(T, 0.6)) * (0.65 + 0.55 * strB)
	if kindB == "crash" or kindB == "ride" and strB > 0.9 then
		Aneed *= 1.5
	end
	if b and b.fill then
		Aneed *= 1.15
	end
	local A = math.min(Aneed, 0.95 * s)
	if not b then
		A = math.min(A, 0.4 * s) -- hit yok: el boşta bekliyor
	end
	local riseT = math.min(0.30, 0.40 * T)
	local fallT = math.min(0.26, 0.52 * T)
	if not b then
		riseT = 0.35
		fallT = 0
	end
	local h = arc(tRel, T, A, riseT, fallT)
	-- yatay ilerleme: yükseliş + bekleme sırasında hedefe varır, düşüşte sabit
	local travelT = (T >= 1e8) and 0.6 or math.max(T - fallT, 1e-3)
	local p = Ease.smootherstep(tRel / travelT)
	local base = tipA:Lerp(tipB, p)
	-- yüzey yüksekliği iki davul arasında yumuşak; ucun yüzeyden en az 0 yukarıda kalması h>=0 ile garanti
	local tip = base + Vector3.new(0, h, 0)
	return tip, h, A, p, a, b
end

-- çubuk yönü: hedefe doğru yatay + eğim (vuruşta ~ -8°, tepede ~ +40° bilekle kalkar)
function DrumLayer._stickDir(self: any, side: string, tip: Vector3, h: number, A: number, shoulderPos: Vector3): Vector3
	local flat = Vector3.new(tip.X - shoulderPos.X, 0, tip.Z - shoulderPos.Z)
	if flat.Magnitude < 0.01 then
		flat = Vector3.new(0, 0, -1)
	end
	flat = flat.Unit
	local frac = math.clamp(h / math.max(self.s * 0.55, 1e-3), 0, 1)
	local pitch = D(-8) + (D(46) - D(-8)) * Ease.smoothstep(frac)
	return Vector3.new(flat.X * math.cos(pitch), math.sin(pitch), flat.Z * math.cos(pitch))
end

-- ───── FAZ 1: olaylar -> kinetik zincir, gövde yönelimi ─────
function DrumLayer.prepare(self: any, perf: any, ctx: any, pose: any)
	local dyn = perf.dyn
	local s = self.s
	-- oturuş: kalça tabureye alçalır
	pose:addRoot(Vector3.new(0, -self.layout.seatDrop, 0))

	for _, e in perf:take("drums", perf.score.drums, ctx.time) do
		local k = e.str * ctx.groove * ctx.style.accentBoost
		local t = e.t
		local kind = e.kind
		local sideSgn = (e.hand == "Right") and 1 or ((e.hand == "Left") and -1 or 0)
		if kind == "kick" then
			perf:at(t + 0.01, function()
				dyn.pelvisY:impulseForPeak(-0.018 * s * k) -- oturan kalça vuruşta çok küçük tepki
				dyn.pelvisShift.x:impulseForPeak(0.006 * s * k)
			end)
			perf:at(t + 0.03, function()
				dyn.waist.x:impulseForPeak(D(0.7) * k)
			end)
		elseif kind == "crash" then
			-- büyük kinetik zincir: kol -> omuz -> üst gövde -> kafa -> ağırlık merkezi
			perf:at(t, function()
				dyn.shoulderL:impulseForPeak(Vector3.new(0.02 * s, -0.06 * s * k, -0.03 * s * k))
			end)
			perf:at(t + 0.03, function()
				dyn.waist.x:impulseForPeak(-D(4.5) * k) -- vuruş sonrası göğüs geriye açılır
				dyn.waist.y:impulseForPeak(D(3.5) * k)
			end)
			perf:at(t + 0.06, function()
				dyn.neck.x:impulseForPeak(D(6) * k * ctx.style.headAmp)
				dyn.neck.y:impulseForPeak(-D(3) * k)
			end)
			perf:at(t + 0.07, function()
				dyn.pelvisY:impulseForPeak(-0.04 * s * k)
				dyn.pelvisShift.x:impulseForPeak(-0.015 * s * k)
			end)
			PerformerState.accent(perf, t, e.str)
		elseif kind == "snare" or kind == "tom" then
			local w = (e.fill and 0.8 or 1) * (e.str >= 0.8 and 1 or 0.55)
			perf:at(t, function()
				local sh = e.hand == "Right" and dyn.shoulderR or dyn.shoulderL
				sh:impulseForPeak(Vector3.new(0, -0.035 * s * k * w, -0.01 * s * k))
			end)
			perf:at(t + 0.03, function()
				dyn.waist.x:impulseForPeak(D(2.2) * k * w)
				dyn.waist.y:impulseForPeak(sideSgn * -D(1.2) * k * w)
			end)
			perf:at(t + 0.055, function()
				dyn.neck.x:impulseForPeak(D(3) * k * w * ctx.style.headAmp)
			end)
			if e.str >= 0.9 then
				perf:at(t + 0.04, function()
					dyn.pelvisY:impulseForPeak(-0.02 * s * k)
				end)
			end
		else -- hat / ride: küçük, hızlı
			perf:at(t, function()
				local sh = e.hand == "Right" and dyn.shoulderR or dyn.shoulderL
				sh:impulseForPeak(Vector3.new(0, -0.01 * s * k, 0))
			end)
			if e.t % (perf.score.beatDur) < 0.02 then
				perf:at(t + 0.04, function()
					dyn.neck.x:impulseForPeak(D(1.4) * k * ctx.style.headAmp)
				end)
			end
		end
	end

	-- gövde yönelimi: aktif elin hedefi (set boyunca yön değiştirir) + öne eğilme (yüksek/uzak vuruşa)
	local sx = 0
	local pitch = 0
	local wsum = 0
	local lateralLook = 0
	local nextBoost = 0
	local shoulderWorld = {}
	for _, side in { "Right", "Left" } do
		local tip, h, A = self:sampleHand(side, ctx.time)
		local center = self.layout.pieces.snare.pos
		local dx = (tip - center):Dot(perf.rig.rootCF:VectorToWorldSpace(Vector3.new(1, 0, 0)))
		local dz = -(tip - center):Dot(perf.rig.rootCF:VectorToWorldSpace(Vector3.new(0, 0, -1)))
		-- yaklaşan vuruşa ağırlık (hand'in şu anki hedefi önemli)
		local wgt = 1 + 0.6 * (h / math.max(A, 1e-3))
		sx += dx * wgt
		wsum += wgt
		pitch += math.max(-dz, 0) * 0 + (tip.Y - center.Y) * 0.0
		nextBoost += math.max(tip.Y - center.Y, 0)
	end
	local meanX = sx / math.max(wsum, 1e-3)
	local yaw = math.clamp(-meanX / (1.4 * s) * D(13), -D(14), D(14))
	perf.bias.waistYaw = yaw * ctx.playW
	perf.bias.neckYaw = -yaw * 0.45 * ctx.playW -- kafa gövdeyi birebir takip etmez: önce hedefe bakar, gövde geriden gelir
	perf.bias.waistPitch = (D(7) + math.clamp(nextBoost / s, 0, 1.2) * D(5)) * ctx.playW * 0.6
	-- bakış: hi-hat/snare'e bak, fill'de toma
	pose.gaze += Vector3.new(D(6) * ctx.playW, -yaw * 0.25, 0)
end

-- ───── FAZ 2: çubuk uçları ve ayak pedalları ─────
local function footSample(kicks: { any }, now: number, s: number, hold: number): (number, number)
	local i = Score.firstIndexAtOrAfter(kicks, now + 1e-9) - 1
	local a, b = kicks[i], kicks[i + 1]
	if not (a and b) then
		return hold, 0
	end
	local T = b.t - a.t
	local A = math.min(0.18 * s, (0.045 + 0.22 * math.min(T, 0.5)) * s) * (0.6 + 0.5 * b.str)
	local lift = arc(now - a.t, T, A, math.min(0.18, 0.4 * T), math.min(0.16, 0.5 * T))
	return math.max(lift, 0), A
end

function DrumLayer.contact(self: any, perf: any, ctx: any, pose: any)
	local s = self.s
	local rig = perf.rig
	local ut = ctx.parts.UpperTorso
	for _, side in { "Right", "Left" } do
		local sh = ctx.parts.UpperTorso * rig.joints[side .. "Shoulder"].c0 * Vector3.zero
		local shoulderPos = (ut * rig.joints[side .. "Shoulder"].c0).Position
		local tip, h, A = self:sampleHand(side, ctx.time)
		local d = self:_stickDir(side, tip, h, A, shoulderPos)
		-- tutuş konumu: ucun gerisinde
		local grip = tip - d * (self.stickLen - self.gripAt)
		-- el yönelimi: parmaklar (-Y) çubuk yönünde, avuç içi aşağı
		local up = Vector3.new(0, 1, 0)
		local palmDown = (-up - d * (-up):Dot(d)).Unit
		local vy = -d
		local vx = (side == "Right") and -palmDown or palmDown
		local vz = vx:Cross(vy)
		local rot = CFrame.fromMatrix(Vector3.zero, vx, vy, vz)
		pose:setHand(side, {
			cf = CFrame.new(grip) * rot,
			grip = CFrame.new(0, 0, 0),
			w = ctx.contactW,
			pole = nil,
			elbowOpen = 0.04 * s,
		})
		self.sticks[side] = { tip = tip, grip = grip, dir = d }
	end

	-- ayaklar: sağ = kick pedalı, sol = hi-hat pedalı
	local pedals = self.layout.pedals
	local stage = rig.rootCF
	local restRot = perf.rest.footRot
	-- kick: öncesinde topuk kalkar (anticipation), vuruşta ayak ucu basar
	local lift, A = footSample(self.kicks, ctx.time, s, 0.02 * s)
	local frac = A > 1e-4 and math.clamp(lift / A, 0, 1) or 0.15
	local pitchR = D(-14) + (D(12) - D(-14)) * frac -- yukarıda ayak ucu kalkık (+), vuruşta bastırılmış (-)
	self.footPitch.Right = pitchR
	self.pedalLift.Right = lift
	pose:setFoot("Right", {
		ankle = pedals.Right + Vector3.new(0, lift + 0.02 * s, 0),
		rot = stage.Rotation * CFrame.Angles(pitchR, 0, 0) * stage.Rotation:Inverse() * restRot.Right,
		w = 1,
	})
	-- hi-hat ayağı: chick (2. ve 4. vuruşta kısa kalkıp basar), open hat'te topuk kalkar
	local hl, hA = footSample(self.hatFoot, ctx.time, s, 0.0)
	local hfrac = hA > 1e-4 and math.clamp(hl / hA, 0, 1) or 0
	self.pedalLift.Left = hl * 0.6
	pose:setFoot("Left", {
		ankle = pedals.Left + Vector3.new(0, hl * 0.6 + 0.0, 0),
		rot = stage.Rotation * CFrame.Angles(D(-6) + D(8) * hfrac, 0, 0) * stage.Rotation:Inverse() * restRot.Left,
		w = 1,
	})
	-- hi-hat ayağı ritim yokken de nazikçe pedalda kalır (pedal hep basılı = kapalı hat)
end

-- Önizleme geometrisi: set + çubuklar + pedal
function DrumLayer.debugGeometry(self: any): { { pts: { Vector3 }, color: string } }
	local geo = {}
	local function circle(center: Vector3, normal: Vector3, r: number, color: string)
		local u = normal:Cross(Vector3.new(0, 1, 0))
		if u.Magnitude < 0.1 then
			u = normal:Cross(Vector3.new(1, 0, 0))
		end
		u = u.Unit
		local v = normal:Cross(u)
		local pts = {}
		for i = 0, 20 do
			local a = i / 20 * math.pi * 2
			table.insert(pts, center + u * (math.cos(a) * r) + v * (math.sin(a) * r))
		end
		table.insert(geo, { pts = pts, color = color })
	end
	for name, p in self.layout.pieces do
		if p.kind == "kick" then
			local fwd = Vector3.new(0, 0, 1) -- yüz davulcuya (+Z) bakar
			circle(p.pos, fwd, p.radius, "#7f8c8d")
			circle(p.pos - fwd * p.thickness, fwd, p.radius, "#7f8c8d")
		elseif p.kind == "head" then
			circle(p.pos, p.normal, p.radius, "#c0392b")
			circle(p.pos - p.normal * p.thickness, p.normal, p.radius, "#c0392b")
		else
			circle(p.pos, p.normal, p.radius, "#f1c40f")
		end
	end
	for _, side in { "Right", "Left" } do
		local st = self.sticks[side]
		table.insert(geo, { pts = { st.grip - st.dir * self.gripAt, st.tip }, color = "#8e5a2b" })
	end
	return geo
end

function Drummer.create(rig: any, opts: { score: any, clock: any, seed: number? })
	return Performer.new(rig, "Drums", {
		score = opts.score, clock = opts.clock, seed = opts.seed,
		instrument = function(perf)
			return DrumLayer.new(perf)
		end,
	})
end

Drummer.Layer = DrumLayer

return Drummer
