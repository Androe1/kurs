--!strict
--[[
	Performer: tek bir R15 karakterinin "müzisyen beyni". Her karakter KENDİ durum makinesine, yaylarına ve
	katmanlarına sahiptir. Enstrümana özel her şey `instrument` katmanından gelir; geri kalan altyapı ortaktır.
	Bu sayede 4. karakter (vokal ya da yeni bir enstrüman) yalnızca yeni bir katman yazarak eklenir.

	Kare akışı (update):
	  1) bağlam (ctx): saat, ölçü/vuruş, bölüm, enerji, durum ağırlıkları, bu karede geçilen vuruşlar
	  2) FAZ 1 (iskelet): katmanlar gövdeyi/kafayı/kalçayı yaylara yazar, enstrüman niyetini hazırlar
	  3) iskelet FK'sı -> enstrüman çerçeveleri artık dünyada bilinir
	  4) FAZ 2 (temas): enstrüman katmanı el/ayak hedeflerini üretir (parmak ucu, çubuk ucu, pedal)
	  5) Etkileşim: IK çözümü + FK karışımı -> Motor6D.Transform; prop'lar güncellenir
	Katmanlar yalnızca Pose'a katkı yapar (Layers/Pose.luau); rig'i yalnızca (5) yazar.
]]

local Root = script:FindFirstAncestor("BandPerformance")
local Config = require(Root.Config)
local SpringM = require(Root.Util.Spring)
local Score = require(Root.Music.Score)
local Ease = require(Root.Util.Ease)
local Pose = require(Root.Layers.Pose)
local Interaction = require(Root.Layers.Interaction)
local PerformerState = require(Root.Performers.PerformerState)
local BaseLayer = require(Root.Layers.Base)
local GrooveLayer = require(Root.Layers.Groove)

local Spring, Spring3 = SpringM.Spring, SpringM.Spring3

export type Layer = {
	name: string,
	prepare: ((any, any, any, any) -> ())?, -- (layer, perf, ctx, pose) faz 1
	contact: ((any, any, any, any) -> ())?, -- (layer, perf, ctx, pose) faz 2
	onBeat: ((any, any, any) -> ())?,
}

local Performer = {}
Performer.__index = Performer

local function sp(name: string): (number, number)
	local c = (Config.springs :: any)[name]
	return c[1], c[2]
end

function Performer.new(rig: any, role: string, opts: { score: any, clock: any, seed: number?, instrument: ((any) -> any)?, profile: any? }): any
	local profile = opts.profile or (Config.profiles :: any)[role]
	local clock = opts.clock
	local self = setmetatable({
		rig = rig,
		role = role,
		profile = profile,
		score = opts.score,
		clock = clock,
		seed = opts.seed or 1,
		layers = {} :: { Layer },
		queue = {} :: { { t: number, fn: () -> () } },
		cursors = {} :: { [string]: number },
		lastT = -1,
		beatCursor = -1,
		props = {} :: { any },
		calm = Spring.new(0, 2.0, 1.0), -- 0..1: sustain/boşluk sırasında hareketi kıs (enstrüman katmanları besler)
		calmTarget = 0,
		bias = { waistPitch = 0, waistYaw = 0, neckYaw = 0 }, -- enstrüman katmanlarının gövdeye verdiği yönelim eğilimi
		seated = false,
		metrics = { reach = {} :: { [string]: number }, handError = { Left = 0, Right = 0 } },
		ikSpring = { Left = Spring.new(0, sp("ikWeight")), Right = Spring.new(0, sp("ikWeight")) },
		debug = {},
	}, Performer) :: any

	-- iskelet yayları
	local f1, z1 = sp("pelvisY")
	self.dyn = {
		pelvisY = Spring.new(0, f1, z1),
		pelvisShift = Spring3.new(Vector3.zero, sp("pelvisShift")),
		pelvisRot = Spring3.new(Vector3.zero, sp("pelvisRot")),
		waist = Spring3.new(Vector3.zero, sp("waist")),
		neck = Spring3.new(Vector3.zero, sp("neck")),
		shoulderL = Spring3.new(Vector3.zero, sp("shoulder")),
		shoulderR = Spring3.new(Vector3.zero, sp("shoulder")),
		energy = Spring.new(0.3, 1.2, 1.0),
		breath = 0,
	}

	-- dinlenme verisi (ayak planı için)
	local rest = rig:forward({})
	self.restParts = table.clone(rest)
	self.rest = {
		ankle = {}, footRot = {},
	}
	for _, side in { "Right", "Left" } do
		local j = rig.joints[side .. "Ankle"]
		self.rest.ankle[side] = (rest[j.part0] * j.c0).Position
		self.rest.footRot[side] = rest[j.part1].Rotation
	end

	PerformerState.init(self)
	-- sıra önemli: Base -> Enstrüman (niyet/bakış) -> Groove (yaylar adımlanır, kafa bakışı okur)
	local baseLayer: any = BaseLayer.new(self)
	table.insert(self.layers, baseLayer)
	if opts.instrument then
		local layer = opts.instrument(self)
		self.instrument = layer
		table.insert(self.layers, layer)
	end
	local grooveLayer: any = GrooveLayer.new(self)
	table.insert(self.layers, grooveLayer)
	return self
end

-- Yumuşatılmış darbe: tek karede hız basamağı yerine 3 parçaya (30/40/30%) ~36 ms'ye yayar. Yaylar doğrusal olduğu için
-- ilk tepe genliği korunur; başlangıç sert "tık" yerine kütleli bir çökme gibi okunur.
function Performer.kick(self: any, t: number, spring: any, amp: number)
	local parts = { { 0, 0.3 }, { 0.018, 0.4 }, { 0.036, 0.3 } }
	for _, p in parts do
		self:at(t + p[1], function()
			spring:impulseForPeak(amp * p[2])
		end)
	end
end

-- ───── zamanlayıcı: olay zamanına bağlı gecikmeli eylem ─────
function Performer.at(self: any, t: number, fn: () -> ())
	table.insert(self.queue, { t = t, fn = fn })
end

function Performer._runQueue(self: any, now: number)
	local q = self.queue
	local i = 1
	while i <= #q do
		local item = q[i]
		if item.t <= now then
			table.remove(q, i)
			item.fn()
		else
			i += 1
		end
	end
end

-- (cursor, now] aralığındaki olayları ver ve imleci ilerlet
function Performer.take(self: any, key: string, list: { any }, now: number): { any }
	local last = self.cursors[key] or now
	self.cursors[key] = now
	if now <= last then
		return {}
	end
	return Score.eventsIn(list, last, now)
end

-- şimdiden itibaren window sn içindeki olaylar (öngörü / anticipation)
function Performer.peek(self: any, list: { any }, now: number, window: number): { any }
	return Score.eventsIn(list, now - 1e-9, now + window)
end

function Performer.resync(self: any, now: number)
	-- seek/atlama: zaman süreksizdir ama poz süreksiz olmasın -> önceki pozdan ~0.35 sn'de yumuşakça geç
	if self.lastTr then
		self.blendFrom = self.lastTr
		self.blendT = 0
	end
	self.queue = {}
	self.cursors = {}
	self.beatCursor = -1
	for _, l in self.layers do
		local rs = (l :: any).resync
		if rs then
			rs(l, self, now)
		end
	end
end

-- ───── bağlam ─────
function Performer._buildCtx(self: any, dt: number, now: number): any
	local clock, score = self.clock, self.score
	local song = score.song
	local bar = clock.bar
	local style = score:barStyle(math.max(bar, 0))
	local sec = score:sectionAtBar(math.max(bar, 0))
	-- bu karede geçilen vuruşlar
	local beats = {}
	if now >= song.firstBarTime then
		local cur = math.floor((now - song.firstBarTime) / score.beatDur)
		local from = self.beatCursor
		if from < 0 then
			from = cur - 1
		end
		if cur - from > 8 then
			from = cur - 1
		end
		for k = from + 1, cur do
			table.insert(beats, { idx = k, inBar = k % 4, bar = k // 4, time = song.firstBarTime + k * score.beatDur })
		end
		self.beatCursor = cur
	end
	local targetEnergy = sec.intensity
	local e = self.dyn.energy:step(targetEnergy, dt)
	local ctx = {
		dt = dt, time = now, bar = bar, beatFloat = clock.beatFloat,
		sec = sec, style = style, beats = beats,
		energy = math.clamp(e, 0, 1),
		playing = clock.playing,
	}
	PerformerState.update(self, ctx)
	return ctx
end

-- ───── ana güncelleme ─────
function Performer.update(self: any, dt: number)
	local now = self.clock.time
	dt = math.clamp(dt, 0, 1 / 20)
	if self.lastT >= 0 and (math.abs(now - self.lastT) > 0.5 or now < self.lastT - 1e-6) then
		self:resync(now)
	end
	local rig = self.rig
	local ctx = self:_buildCtx(dt, now)
	self:_runQueue(now)

	local pose = Pose.new()
	-- FAZ 1
	for _, l in self.layers do
		local f = (l :: any).prepare
		if f then
			f(l, self, ctx, pose)
		end
	end
	-- iskelet transformları
	local tr: { [string]: CFrame } = {}
	tr.Root = CFrame.new(pose.rootOffset) * pose.rootRot
	tr.Waist = pose.rot.Waist or CFrame.identity
	tr.Neck = pose.rot.Neck or CFrame.identity
	local parts = rig:forward(tr)
	ctx.parts = parts
	-- FAZ 2
	for _, l in self.layers do
		local f = (l :: any).contact
		if f then
			f(l, self, ctx, pose)
		end
	end
	-- Etkileşim (IK + FK karışımı)
	Interaction.solve(self, pose, tr, parts, dt)
	if self.blendFrom then
		self.blendT += dt / 0.35
		local w = Ease.smootherstep(self.blendT)
		for name, cf in tr do
			local from = self.blendFrom[name]
			if from then
				tr[name] = from:Lerp(cf, w)
			end
		end
		if self.blendT >= 1 then
			self.blendFrom = nil
		end
	end
	rig:apply(tr)
	local finalParts = rig:forward(tr)
	self.parts = finalParts
	self.lastTr = tr
	ctx.finalParts = finalParts
	-- temas hatası ölçümü
	for _, side in { "Right", "Left" } do
		local h = (pose.hands :: any)[side]
		if h and h.w > 0.98 and self.ikSpring[side].x > 0.97 then
			local handCF = finalParts[side .. "Hand"]
			self.metrics.handError[side] = ((handCF * h.grip).Position - h.cf.Position).Magnitude
		else
			self.metrics.handError[side] = 0
		end
	end
	-- prop'lar
	for _, p in self.props do
		p:update(self, ctx, pose)
	end
	self.ctx = ctx
	self.pose = pose
	self.lastT = now
end

-- eklem çerçevesi yardımcıları (katmanlar için)
function Performer.partCF(self: any, ctx: any, name: string): CFrame
	return ctx.parts[name]
end

return Performer
