-- Band Performance kurulumu: Studio > View > Command Bar'a yapıştır, Enter.
local RS, SSS, SPS = game:GetService("ReplicatedStorage"), game:GetService("ServerScriptService"), game:GetService("StarterPlayer").StarterPlayerScripts
for _, p in {RS:FindFirstChild("BandPerformance"), SSS:FindFirstChild("BandServer"), SPS:FindFirstChild("BandClient")} do p:Destroy() end
local function mk(parent, cls, name, src) local i = Instance.new(cls) i.Name = name if src then i.Source = src end i.Parent = parent return i end
local root
root = mk(RS, "ModuleScript", "BandPerformance", [===[
--!strict
--[[
	BandPerformance - Roblox R15 canlı grup performans sistemi (prosedürel, katmanlı, müziğe kilitli).

	Kullanım (istemci):
		local BandPerformance = require(ReplicatedStorage.BandPerformance)
		local band = BandPerformance.new({
			models = workspace.Band:GetChildren(),   -- ya da BandRole attribute'lu modeller (discover)
			timeSource = BandPerformance.soundTimeSource(workspace.BandSong),
		})
		RunService:BindToRenderStep("Band", Enum.RenderPriority.Last.Value, function(dt) band:update(dt) end)

	Roller: Guitar, Bass, Drums, Vocal. Yeni rol eklemek: BandPerformance.registerRole("Keys", factory)
	factory(rig, {score, clock, seed}) -> Performer ve (isteğe) prop türü.
]]

local Root = script
local Config = require(Root.Config)
local Rng = require(Root.Util.Rng)
local Score = require(Root.Music.Score)
local Clock = require(Root.Music.Clock)
local R15Rig = require(Root.Rig.R15Rig)
local RigPrep = require(Root.Rig.RigPrep)
local PropBuilder = require(Root.Props.PropBuilder)
local Guitarist = require(Root.Performers.Guitarist)
local Bassist = require(Root.Performers.Bassist)
local Drummer = require(Root.Performers.Drummer)
local Vocalist = require(Root.Performers.Vocalist)

export type Band = {
	clock: any,
	score: any,
	performers: { [string]: any },
	order: { string },
	props: { any },
	update: (Band, number) -> (),
	seek: (Band, number) -> (),
	destroy: (Band) -> (),
}

local BandPerformance = {}
BandPerformance.__index = BandPerformance
BandPerformance.Config = Config
BandPerformance.CameraRig = require(Root.CameraRig)
BandPerformance.PropBuilder = PropBuilder
BandPerformance.Performer = require(Root.Performers.Performer)
BandPerformance.Pose = require(Root.Layers.Pose)

local ROLES: { [string]: (any, any) -> any } = {
	Guitar = Guitarist.create,
	Bass = Bassist.create,
	Drums = Drummer.create,
	Vocal = Vocalist.create,
}

-- Yeni performer rolü ekle (4. karakter için modüler genişleme noktası)
function BandPerformance.registerRole(role: string, factory: (any, any) -> any)
	ROLES[role] = factory
end

-- Bir konteynerdeki R15 modelleri rolleriyle bul: BandRole attribute'u ya da Config.MODEL_NAMES
function BandPerformance.discover(container: Instance): { { model: any, role: string } }
	local out = {}
	for _, m in container:GetChildren() do
		if m:IsA("Model") and m:FindFirstChild("HumanoidRootPart", true) then
			local role = m:GetAttribute(Config.ROLE_ATTRIBUTE) or (Config.MODEL_NAMES :: any)[m.Name]
			if role and ROLES[role] then
				table.insert(out, { model = m, role = role })
			end
		end
	end
	return out
end

-- Zaman kaynakları. Dönüş: () -> (şarkı zamanı | nil, çalıyor mu)
function BandPerformance.soundTimeSource(sound: any): () -> (number?, boolean)
	return function()
		if sound and sound.IsPlaying then
			return sound.TimePosition, true
		end
		return nil, false
	end
end

-- Sunucunun yazdığı başlangıç zamanı (workspace attribute, GetServerTimeNow tabanlı): tüm istemciler aynı kareyi görür
function BandPerformance.serverTimeSource(workspaceRef: any): () -> (number?, boolean)
	return function()
		local start = workspaceRef:GetAttribute(Config.START_ATTRIBUTE)
		if type(start) == "number" then
			local t = workspaceRef:GetServerTimeNow() - start
			return t, t >= 0
		end
		return nil, false
	end
end

function BandPerformance.manualTimeSource(): (() -> (number?, boolean), (number?) -> ())
	local state = { t = 0 :: number?, playing = false }
	return function()
		return state.t, state.playing
	end, function(t: number?)
		state.t = t
		state.playing = t ~= nil
	end
end

--[[ opts:
	models: { Model } | { {model, role} }   (yoksa discover(container))
	container: Instance?                     discover için
	song: SongMap tablosu (varsayılan Data.SongMap)
	timeSource: () -> (number?, boolean)
	buildProps: boolean (varsayılan true), propsParent: Instance?
	autoFacing: Config.profiles[role].facing kadar karakteri döndür (varsayılan false)
	seed: number
	getCameraPosition: () -> Vector3?   LOD için kamera konumu (yoksa her performer her kare güncellenir)
	cullDistance: number                 bu uzaklıktan uzak performer güncellenmez (varsayılan 220 stud); geri gelince yumuşak geçişle senkronlanır
]]
function BandPerformance.new(opts: any): Band
	opts = opts or {}
	local song = opts.song or require(Root.Data.SongMap)
	local score = Score.build(song, opts.seed or 20240601)
	local clock = Clock.new(song, Config.VISUAL_LEAD)
	local entries = opts.entries
	if entries == nil then
		entries = {}
		for _, m in (opts.models or {}) do
			local model = (m.ClassName ~= nil) and m or m.model
			local role = (m.ClassName == nil and m.role) or model:GetAttribute(Config.ROLE_ATTRIBUTE) or (Config.MODEL_NAMES :: any)[model.Name]
			if role and ROLES[role] then
				table.insert(entries, { model = model, role = role })
			end
		end
		if opts.container then
			for _, e in BandPerformance.discover(opts.container) do
				table.insert(entries, e)
			end
		end
	end

	local self = setmetatable({
		song = song,
		clock = clock,
		score = score,
		performers = {},
		order = {},
		props = {},
		getCameraPosition = opts.getCameraPosition,
		cullDistance = opts.cullDistance or 220,
		timeSource = opts.timeSource or (function(): (number?, boolean) return nil, false end),
		freeRun = opts.freeRun == true,
		time = 0,
	}, BandPerformance)

	local propsParent = opts.propsParent
	for _, e in entries do
		RigPrep.prepare(e.model)
		local hrp = e.model:FindFirstChild("HumanoidRootPart", true) :: any
		if opts.autoFacing and hrp then
			local profile = (Config.profiles :: any)[e.role]
			if profile then
				hrp.CFrame = hrp.CFrame * CFrame.Angles(0, profile.facing, 0)
			end
		end
		local rig = R15Rig.new(e.model)
		rig:reset() -- önceki bir animasyondan kalan Transform'lar dinlenme pozunu bozmasın
		local perf = ROLES[e.role](rig, {
			score = score, clock = clock, seed = Rng.seedFromString(e.model.Name),
		})
		perf.model = e.model
		self.performers[e.role] = perf
		table.insert(self.order, e.role)
		if opts.buildProps ~= false then
			local parent = propsParent or e.model
			local existing = e.model:FindFirstChild(e.role .. "_Prop")
			local prop
			if existing then
				prop = PropBuilder.adopt(existing, e.role, perf)
			else
				prop = PropBuilder.build(e.role, perf, parent)
			end
			table.insert(perf.props, prop)
			table.insert(self.props, prop)
		end
	end
	return (self :: any) :: Band
end

function BandPerformance.update(self: any, dt: number)
	local t, playing = self.timeSource()
	if self.freeRun then
		self.clock:update(dt, nil, true)
	else
		self.clock:update(dt, t, playing)
	end
	local camPos = self.getCameraPosition and self.getCameraPosition() or nil
	for _, role in self.order do
		local p = self.performers[role]
		if camPos ~= nil and (p.rig.rootCF.Position - camPos).Magnitude > self.cullDistance then
			p.culled = true -- uzak: güncelleme yok (CPU tasarrufu); yakına gelince update() zaman sıçramasını görüp yumuşakça yeniden senkronlar
		else
			p.culled = false
			p:update(dt)
		end
	end
end

function BandPerformance.seek(self: any, t: number)
	self.clock:seek(t)
end

function BandPerformance.getPerformer(self: any, role: string): any
	return self.performers[role]
end

-- hata ayıklama: performer başına temas hatası ve durum
function BandPerformance.getMetrics(self: any): { [string]: any }
	local out = {}
	for role, p in self.performers do
		out[role] = { state = p.state, handError = p.metrics.handError, reach = p.metrics.reach }
	end
	return out
end

function BandPerformance.destroy(self: any)
	for _, role in self.order do
		local p = self.performers[role]
		p.rig:reset()
		for _, prop in p.props do
			prop:destroy()
		end
	end
	self.performers = {}
	self.order = {}
end

return BandPerformance
]===])
mk(root, "ModuleScript", "CameraRig", [===[
--!strict
--[[
	Kamera yönetmeni: performansı birçok açıdan doğrulamak/çekmek için hazır planlar.
	Planlar sahne yönüne ve gruba/performer'a göre hesaplanır (karakterler hangi yöne bakarsa baksın doğru çıkar):
	  front, threeQuarterFront, side, threeQuarterBack, handsCloseUp, guitarSide, bassSide, drummerSide, lowAngle, elevated
	Kullanım:
		local rig = CameraRig.new()
		rig:cut("guitarSide", band)           -- anında kesme
		RunService:BindToRenderStep("Cam", Enum.RenderPriority.Camera.Value + 1, function(dt)
			camera.CFrame = rig:update(dt, band)
		end)
	Otomatik yönetmen: rig:direct(band) bölüm/ölçü sınırlarında kesme yapar (müziğe göre).
]]

local Root = script.Parent
local SpringM = require(Root.Util.Spring)
local Rng = require(Root.Util.Rng)
local Config = require(Root.Config)

local Spring3 = SpringM.Spring3

local CameraRig = {}
CameraRig.__index = CameraRig

local UP = Vector3.new(0, 1, 0)

local function bandFrame(band: any): (Vector3, Vector3, Vector3, number)
	-- merkez, sahne ileri (izleyiciye doğru = karakterlerin baktığı yön), sahne sağı, yarıçap
	local sum, fwd, n = Vector3.zero, Vector3.zero, 0
	for _, role in band.order do
		local p = band.performers[role]
		local cf = p.rig.rootCF
		sum += cf.Position
		fwd += cf.LookVector
		n += 1
	end
	if n == 0 then
		return Vector3.zero, Vector3.new(0, 0, -1), Vector3.new(1, 0, 0), 10
	end
	local c = sum / n
	local f = Vector3.new(fwd.X, 0, fwd.Z)
	f = f.Magnitude > 1e-3 and f.Unit or Vector3.new(0, 0, -1)
	local r = f:Cross(UP) -- ileri x yukarı = sağ (karakter -Z'ye bakarken +X)
	local radius = 6
	for _, role in band.order do
		radius = math.max(radius, (band.performers[role].rig.rootCF.Position - c).Magnitude + 4)
	end
	return c + UP * 3, f, r, radius
end

local function subject(band: any, role: string): any
	return band.performers[role]
end

-- Dönüş: (kamera konumu, bakılan nokta)
local SHOTS: { [string]: (any, string?) -> (Vector3, Vector3) } = {}

SHOTS.front = function(band)
	local c, f, r, rad = bandFrame(band)
	return c + f * (rad * 1.5) + UP * 0.5, c
end
SHOTS.threeQuarterFront = function(band)
	local c, f, r, rad = bandFrame(band)
	return c + (f * 0.8 + r * 0.6).Unit * (rad * 1.4) + UP * 1.2, c
end
SHOTS.side = function(band)
	local c, f, r, rad = bandFrame(band)
	return c + r * (rad * 1.5) + UP * 0.5, c
end
SHOTS.threeQuarterBack = function(band)
	local c, f, r, rad = bandFrame(band)
	return c + (-f * 0.8 + r * 0.6).Unit * (rad * 1.4) + UP * 1.8, c + f * 2
end
SHOTS.lowAngle = function(band)
	local c, f, r, rad = bandFrame(band)
	return c + (f * 0.9 + r * 0.3).Unit * (rad * 1.2) - UP * 1.6, c + UP * 1.2
end
SHOTS.elevated = function(band)
	local c, f, r, rad = bandFrame(band)
	return c + (f * 0.7 - r * 0.3).Unit * (rad * 1.1) + UP * (rad * 0.8), c - UP * 0.5
end

-- performer'a bağlı planlar: omuz hizasında yan çekim (el/boyun/gövde net görünür)
local function sideOf(band: any, role: string, side: number, dist: number, height: number): (Vector3, Vector3)
	local p = subject(band, role)
	if not p or not p.parts then
		return SHOTS.front(band)
	end
	local ut = p.parts.UpperTorso
	local pos = ut.Position
	local r = p.rig.rootCF.RightVector
	return pos + r * (side * dist) + UP * height, pos - UP * 0.4
end
SHOTS.guitarSide = function(band) return sideOf(band, "Guitar", 1, 7, 0.4) end
SHOTS.bassSide = function(band) return sideOf(band, "Bass", 1, 7, 0.4) end
SHOTS.drummerSide = function(band) return sideOf(band, "Drums", 1, 8, 0.8) end
SHOTS.handsCloseUp = function(band, role)
	local p = subject(band, role or "Guitar")
	if not p or not p.parts then
		return SHOTS.front(band)
	end
	local lh = p.parts.LeftHand.Position
	local rh = p.parts.RightHand.Position
	local mid = (lh + rh) / 2
	local fwd = p.rig.rootCF.LookVector
	return mid - fwd * 3.2 + UP * 0.6 + p.rig.rootCF.RightVector * 0.8, mid
end

CameraRig.SHOTS = SHOTS

function CameraRig.new(): any
	return setmetatable({
		pos = Spring3.new(Vector3.new(0, 5, 20), 3.2, 0.9),
		look = Spring3.new(Vector3.zero, 4.5, 1.0),
		shot = "front",
		role = nil :: string?,
		lastDirectBar = -99,
		fov = 55,
		handheld = 0.0, -- 0..1 el kamerası titremesi
		t = 0,
	}, CameraRig)
end

function CameraRig.target(self: any, band: any): (Vector3, Vector3)
	local f = SHOTS[self.shot] or SHOTS.front -- bilinmeyen plan adı çökertmesin
	return f(band, self.role)
end

-- plan adını normalize et (büyük/küçük harf farkı); geçersizse nil
function CameraRig.resolve(name: string): string?
	local lower = string.lower(name)
	for k in SHOTS do
		if string.lower(k) == lower then
			return k
		end
	end
	return nil
end

function CameraRig.cut(self: any, shot: string, band: any, role: string?)
	self.shot = CameraRig.resolve(shot) or "front"
	self.role = role
	local p, l = self:target(band)
	self.pos:reset(p)
	self.look:reset(l)
end

function CameraRig.setShot(self: any, shot: string, role: string?)
	self.shot = CameraRig.resolve(shot) or "front"
	self.role = role
end

-- Otomatik yönetmen: 2 ölçülük planlar, bölüm sınırlarında kesme, nakaratta yakın/alçak/yan planlar
function CameraRig.direct(self: any, band: any)
	local bar = math.floor(band.clock.bar)
	if bar == self.lastDirectBar or bar < 0 then
		return
	end
	local sec = band.score:sectionAtBar(bar)
	local isCut = (bar - sec.startBar) % 2 == 0
	if not isCut then
		return
	end
	self.lastDirectBar = bar
	local seed = band.score.seed
	local h = Rng.hash(seed, bar, 77)
	local list
	if sec.kind == "intro" or sec.kind == "outro" then
		list = { { "front" }, { "threeQuarterFront" }, { "elevated" } }
	elseif sec.kind == "chorus" then
		list = {
			{ "lowAngle" }, { "side" }, { "handsCloseUp", "Guitar" }, { "drummerSide" }, { "bassSide" },
			{ "guitarSide" }, { "threeQuarterBack" }, { "handsCloseUp", "Bass" }, { "threeQuarterFront" },
		}
	else
		list = { { "threeQuarterFront" }, { "front" }, { "guitarSide" }, { "handsCloseUp", "Guitar" }, { "elevated" } }
	end
	local pick = list[1 + math.floor(h * #list)]
	self:cut(pick[1], band, pick[2])
end

-- Kamera CFrame'i (yaylı takip + hafif el kamerası); dt ile ilerler
function CameraRig.update(self: any, dt: number, band: any): CFrame
	self.t += dt
	local p, l = self:target(band)
	local pos = self.pos:step(p, dt)
	local look = self.look:step(l, dt)
	if self.handheld > 0 then
		local k = self.handheld
		pos += Vector3.new(math.sin(self.t * 1.7), math.sin(self.t * 2.3 + 1), math.sin(self.t * 1.3 + 2)) * (0.035 * k)
	end
	return CFrame.lookAt(pos, look)
end

return CameraRig
]===])
mk(root, "ModuleScript", "Config", [===[
--!strict
--[[
	Tüm ayarlar burada. Hareketin "karakteri" (ağır/hafif, ne kadar sallanır, ne kadar abartılır)
	rol profillerinde; sahne yerleşimi Stage'de. Birim: stud, saniye, radyan (açılar derece yazılıp çevrilir).
	Etiketler (tag) ve model adları: workspace'te "BandRole" attribute'u (Guitar/Bass/Drums/Vocal) olan
	R15 modelleri otomatik bulunur; yoksa Models adlarına bakılır.
]]

local Config = {}

Config.TAG = "BandMember"
Config.ROLE_ATTRIBUTE = "BandRole"
-- model adı -> rol (BandRole attribute'u yoksa)
Config.MODEL_NAMES = {
	Gitarist = "Guitar", Gitarsit = "Guitar", Guitarist = "Guitar",
	Basgitar = "Bass", Basist = "Bass", Basci = "Bass", Bassist = "Bass",
	Baterist = "Drums", Batersit = "Drums", Drummer = "Drums",
	Vokalist = "Vocal", Vocalist = "Vocal",
}

-- şarkı başlangıç zamanı (sunucu saati) workspace attribute'u: Band sunucusu yazar, istemciler okur
Config.START_ATTRIBUTE = "BandStartServerTime"
Config.SOUND_NAME = "BandSong" -- workspace'te bu adda bir Sound varsa saat ona kilitlenir

-- Müzikal zaman: görsel vuruş ses vuruşunun ne kadar önünde (sn). + = animasyon erken. Ses gecikmesini telafi eder.
Config.VISUAL_LEAD = 0.02

local function deg(d: number): number
	return math.rad(d)
end
Config.deg = deg

--[[ Rol profilleri. Çarpanlar enerji (0..1) ile ölçeklenir.
	bounce   : vuruşta kalça çökmesi (stud)       sway : yavaş ağırlık aktarımı genliği (stud)
	nod      : vuruşta kafa yatışı (rad)          lean : ileri/geri eğilme (rad)
	chestCounter: göğüs karşı dönüşü oranı        head* : kafanın torsoyu "önceden" yönlendirmesi
	weightPeriodBars: ağırlık transferi periyodu  stance: ayak aralığı/açısı
]]
Config.profiles = {
	Guitar = {
		bounce = 0.075, bounceDelay = 0.0, sway = 0.15, nod = deg(7), lean = deg(5), chestCounter = 0.6,
		headLead = 0.35, weightPeriodBars = 2, footTap = 0.6, strapDrop = 0.0,
		stanceYaw = deg(24), stanceWidth = 1.15,
		-- karakterin sahnedeki "performans yönü" (yaw, derece): davulcuya/kameraya hafif dönük
		facing = deg(-18),
	},
	Bass = {
		-- bas: daha ağır, daha az ama güçlü hareket; kalça/gövde groove'u, sustain'de sakin
		bounce = 0.05, bounceDelay = 0.012, sway = 0.12, nod = deg(5), lean = deg(3), chestCounter = 0.8,
		headLead = 0.2, weightPeriodBars = 4, footTap = 0.35, strapDrop = 0.0,
		stanceYaw = deg(18), stanceWidth = 1.3,
		facing = deg(22),
	},
	Drums = {
		bounce = 0.0, bounceDelay = 0.0, sway = 0.0, nod = deg(8), lean = deg(7), chestCounter = 0.5,
		headLead = 0.3, weightPeriodBars = 4, footTap = 0.0, strapDrop = 0.0,
		stanceYaw = 0, stanceWidth = 1.0, facing = 0,
	},
	Vocal = {
		bounce = 0.06, bounceDelay = 0.0, sway = 0.2, nod = deg(8), lean = deg(7), chestCounter = 0.7,
		headLead = 0.5, weightPeriodBars = 2, footTap = 0.4, strapDrop = 0.0,
		stanceYaw = deg(14), stanceWidth = 1.2, facing = deg(0),
	},
}

-- Yay parametreleri (freq Hz, damping ζ). Sert gövde -> gevşek uç: lead & follow kendiliğinden doğar.
Config.springs = {
	pelvisY = { 3.4, 0.42 },
	pelvisShift = { 2.2, 0.8 },
	pelvisRot = { 3.0, 0.7 },
	waist = { 3.8, 0.6 },
	neck = { 4.6, 0.5 },
	shoulder = { 5.5, 0.55 },
	hand = { 6.0, 0.5 },
	elbow = { 4.5, 0.6 },
	instrument = { 4.0, 0.45 },
	ikWeight = { 1.4, 1.0 },
}

-- Eklem hareket sınırları (güvenlik; anatomik saçmalık olmasın)
Config.limits = {
	waistPitch = deg(35), waistYaw = deg(32), waistRoll = deg(20),
	neckPitch = deg(40), neckYaw = deg(55), neckRoll = deg(22),
	wrist = deg(80), ankle = deg(50), rootRoll = deg(12), rootYaw = deg(30),
	elbowFlexMax = deg(150), kneeFlexMax = deg(145),
}

-- Kamera yardımcı ön ayarları (CameraRig): torso/instrument'a göre
Config.cameraShots = {
	"front", "threeQuarterFront", "side", "threeQuarterBack",
	"handsCloseUp", "guitarSide", "bassSide", "drummerSide", "lowAngle", "elevated",
}

return Config
]===])
local F_Music = mk(root, "Folder", "Music")
mk(F_Music, "ModuleScript", "Clock", [===[
--!strict
--[[
	Müzik saati. Üç kaynaktan şarkı zamanını türetir (öncelik sırasıyla):
	  1) workspace'teki "BandSong" Sound'unun TimePosition'ı (ses ne zaman başlarsa)
	  2) sunucunun yazdığı başlangıç zamanı (workspace:GetServerTimeNow() - start)
	  3) elle ilerletme (testler, çevrimdışı önizleme)

	Sound.TimePosition kaba güncellenir (kare kare sıçrar) -> kendi zamanımızı dt ile ilerletip ölçüme
	yumuşakça yaklaştırırız (drift düzeltme); çok farklıysa (seek/lag) bir anda atlarız.
]]

export type Clock = {
	song: any,
	time: number, -- şarkı zamanı (sn), animasyon için (VISUAL_LEAD dahil)
	rawTime: number,
	bar: number, -- ondalıklı ölçü (0 = ilk ölçü başı)
	beatFloat: number, -- ondalıklı vuruş (ölçü içinde 0..4)
	slotDur: number,
	beatDur: number,
	barDur: number,
	playing: boolean,
	lead: number,
}

local Clock = {}
Clock.__index = Clock

function Clock.new(song: any, lead: number?): Clock
	local beatDur = 60 / song.bpm
	local self = setmetatable({
		song = song,
		time = 0,
		rawTime = 0,
		bar = 0,
		beatFloat = 0,
		beatDur = beatDur,
		barDur = beatDur * song.beatsPerBar,
		slotDur = beatDur * song.beatsPerBar / song.slotsPerBar,
		playing = false,
		lead = lead or 0,
	}, Clock)
	return self :: any
end

function Clock.slotTime(self: Clock, slot: number): number
	return self.song.firstBarTime + slot * self.slotDur
end

function Clock.barTime(self: Clock, bar: number): number
	return self.song.firstBarTime + bar * self.barDur
end

-- measured: ölçülen şarkı zamanı (nil = kaynak yok, kendi saatiyle ilerle). playing: şarkı çalıyor mu
function Clock.update(self: Clock, dt: number, measured: number?, playing: boolean?)
	local isPlaying = playing ~= false and measured ~= nil or playing == true
	self.playing = isPlaying
	if measured ~= nil then
		local err = measured - self.rawTime
		if math.abs(err) > 0.25 or not isPlaying then
			self.rawTime = measured -- seek ya da duraklama: kilitlen
		else
			self.rawTime += dt + err * math.min(1, dt * 8) -- yumuşak drift düzeltme
		end
	elseif isPlaying then
		self.rawTime += dt
	end
	self.time = self.rawTime + self.lead
	local song = self.song
	self.bar = (self.time - song.firstBarTime) / self.barDur
	self.beatFloat = (self.bar % 1) * song.beatsPerBar
end

function Clock.seek(self: Clock, t: number)
	self.rawTime = t
	self.time = t + self.lead
	self.bar = (self.time - self.song.firstBarTime) / self.barDur
	self.beatFloat = (self.bar % 1) * self.song.beatsPerBar
end

return Clock
]===])
mk(F_Music, "ModuleScript", "Score", [===[
--!strict
--[[
	SongMap (analyze_song.py çıktısı) -> performans "notası".

	SongMap ölçülen şeydir: tempo ızgarası, 16'lık başına davul/gitar bandı enerjisi, yarım ölçü başına akor kökü,
	vuruş başına bas notası. Burada bu ölçümler çalınabilir OLAYLARA çevrilir:
	  drums  : kick / snare / hat / hatOpen / crash / ride / tom (şiddetli, kol atamalı)
	  guitar : strum ızgarası (down/up/ghost/mute/accent) + akor değişimleri (perde = fret)
	  bass   : pluck olayları (tel/perde/parmak/süre) - boşluklar korunur
	Ölçüm gürültülüyse (distorsiyonlu miks) davul için ölçümü stil önceliğiyle (prior) birleştiririz; ağırlıklı
	olarak ölçüm kazanır. Bu bir transkripsiyon değil: tutarlı, müzikle ilişkili bir performans iskeleti.
]]

local Root = script:FindFirstAncestor("BandPerformance")
local Rng = require(Root.Util.Rng)
local DrumKit = require(Root.Performers.DrumKit)

export type Section = {
	index: number, startBar: number, endBar: number, startT: number, endT: number,
	kind: string, intensity: number,
}

export type DrumEvent = { t: number, slot: number, kind: string, str: number, drum: string, hand: string?, fill: boolean?, dropped: boolean?, hit: any? }
export type StrumEvent = { t: number, slot: number, dir: number, str: number, kind: string }
export type ChordEvent = { t: number, bar: number, pc: number, quality: string, fret: number, string: number }
export type BassEvent = { t: number, slot: number, midi: number, str: number, string: number, fret: number, dur: number, finger: number }
export type BarStyle = {
	bar: number, cycle: number, phase: number, accentBoost: number, headAmp: number,
	stanceShift: boolean, fill: boolean, hold: boolean, swayDir: number, vocalOn: boolean,
	swayMul: number, bounceMul: number, leanMul: number,
}

export type Score = {
	song: any, seed: number,
	slotDur: number, barDur: number, beatDur: number,
	sections: { Section },
	drums: { DrumEvent }, guitar: { StrumEvent }, chords: { ChordEvent }, bass: { BassEvent },
	barStyles: { BarStyle },
}

local Score = {}

local function lane(str: string, slot: number): number
	local c = string.sub(str, slot + 1, slot + 1)
	if c == "." or c == "" then
		return 0
	end
	return (tonumber(c) or 0) / 9
end

-- ───── bölümler ─────
local function buildSections(song: any, slotDur: number, barDur: number): { Section }
	local starts = song.sectionStarts
	local out: { Section } = {}
	local energy = song.energy
	local means = {}
	local lo, hi = 1e9, -1e9
	for i, s in starts do
		local e = (starts[i + 1] or song.bars) - 1
		local sum = 0
		for b = s, e do
			sum += energy[b + 1] or 0
		end
		local mean = sum / math.max(1, e - s + 1)
		means[i] = mean
		lo, hi = math.min(lo, mean), math.max(hi, mean)
	end
	for i, s in starts do
		local e = starts[i + 1] or song.bars
		local m = means[i]
		local norm = (m - lo) / math.max(hi - lo, 1e-6)
		local kind = "verse"
		if i == 1 then
			kind = "intro"
		elseif i == #starts then
			kind = "outro"
		elseif norm > 0.62 then
			kind = "chorus"
		elseif norm < 0.3 then
			kind = "calm"
		end
		table.insert(out, {
			index = i, startBar = s, endBar = e,
			startT = song.firstBarTime + s * barDur, endT = song.firstBarTime + e * barDur,
			kind = kind, intensity = 0.3 + 0.7 * norm,
		})
	end
	return out
end

function Score.sectionAtBar(self: Score, bar: number): Section
	for _, s in self.sections do
		if bar >= s.startBar and bar < s.endBar then
			return s
		end
	end
	return self.sections[#self.sections]
end

-- ───── davul ─────
local PRIOR = {
	intro = { k = { [0] = 1 }, s = {}, h = { [0] = 0.6, [4] = 0.6, [8] = 0.6, [12] = 0.6 } },
	calm = { k = { [0] = 1, [10] = 0.6 }, s = { [4] = 0.8, [12] = 0.8 }, h = { [0] = 0.5, [4] = 0.5, [8] = 0.5, [12] = 0.5 } },
	verse = { k = { [0] = 1, [10] = 0.7 }, s = { [4] = 1, [12] = 1 }, h = { [0] = 0.6, [2] = 0.5, [4] = 0.6, [6] = 0.5, [8] = 0.6, [10] = 0.5, [12] = 0.6, [14] = 0.5 } },
	chorus = { k = { [0] = 1, [2] = 0.6, [8] = 0.7, [10] = 0.7 }, s = { [4] = 1, [12] = 1 }, h = { [0] = 0.7, [2] = 0.55, [4] = 0.7, [6] = 0.55, [8] = 0.7, [10] = 0.55, [12] = 0.7, [14] = 0.55 } },
	outro = { k = { [0] = 1 }, s = { [4] = 0.7, [12] = 0.7 }, h = { [0] = 0.5, [4] = 0.5, [8] = 0.5, [12] = 0.5 } },
}

local FILL_PATTERNS = {
	-- slot, drum
	{ { 10, "snare" }, { 11, "tom1" }, { 12, "tom1" }, { 13, "tom2" }, { 14, "floor" }, { 15, "floor" } },
	{ { 12, "tom1" }, { 13, "tom1" }, { 14, "tom2" }, { 15, "floor" } },
	{ { 8, "snare" }, { 10, "tom1" }, { 11, "tom2" }, { 12, "tom2" }, { 13, "floor" }, { 14, "floor" }, { 15, "snare" } },
}

local function buildDrums(song: any, seed: number, sections: { Section }, slotDur: number): { DrumEvent }
	local ev: { DrumEvent } = {}
	local spb = song.slotsPerBar
	local sectionStartBars: { [number]: Section } = {}
	for _, s in sections do
		sectionStartBars[s.startBar] = s
	end
	local lastSectionBar = sections[#sections].startBar
	for bar = 0, song.bars - 1 do
		local ln = song.lanes[bar + 1]
		local sec = nil
		for _, s in sections do
			if bar >= s.startBar and bar < s.endBar then
				sec = s
			end
		end
		local kind = sec and sec.kind or "verse"
		local prior = PRIOR[kind] or PRIOR.verse
		-- bir sonraki ölçü yeni bölüm mü / 4 ölçülük cümle sonu: fill adayı
		local nextIsSection = sectionStartBars[bar + 1] ~= nil
		local isFillBar = nextIsSection and bar + 1 < song.bars and kind ~= "outro"
			or (kind == "chorus" and bar % 8 == 7 and Rng.chance(seed, bar, 11, 0.6))
		local fillSlot0 = 99
		local fillList
		if isFillBar then
			fillList = FILL_PATTERNS[1 + math.floor(Rng.hash(seed, bar, 5) * #FILL_PATTERNS)]
			fillSlot0 = fillList[1][1]
		end
		local barBase = bar * spb
		for slot = 0, spb - 1 do
			local gslot = barBase + slot
			local t = song.firstBarTime + gslot * slotDur
			if slot < fillSlot0 then
				local kv = math.max((prior.k[slot] or 0) * 0.7, lane(ln.k, slot))
				-- backbeat/ana vuruşlarda ölçüm düşükse bile stil kazansın (distorsiyon masker)
				if kv >= 0.42 then
					table.insert(ev, { t = t, slot = gslot, kind = "kick", str = math.clamp(kv, 0.45, 1), drum = "kick" })
				end
				local sv = math.max((prior.s[slot] or 0) * 0.75, lane(ln.s, slot))
				if sv >= 0.45 and (slot % 4 == 0 or lane(ln.s, slot) >= 0.55) then
					local ghost = (prior.s[slot] == nil) and sv < 0.7
					table.insert(ev, { t = t, slot = gslot, kind = "snare", str = ghost and 0.3 or math.clamp(sv, 0.55, 1), drum = "snare" })
				end
				-- crash: ölçüm yüksek ya da bölüm başı
				local isSecStart = slot == 0 and sectionStartBars[bar] ~= nil and bar > 0
				local cv = lane(ln.c, slot)
				if isSecStart or cv >= 0.55 then
					table.insert(ev, { t = t, slot = gslot, kind = "crash", str = isSecStart and 1.0 or 0.8, drum = "crash" })
				else
					-- hi-hat / ride: bölüm yoğunluğuna göre
					local hv = math.max((prior.h[slot] or 0) * 0.8, lane(ln.h, slot))
					local ride = kind == "chorus" and bar % 8 >= 4
					if hv >= 0.45 and (slot % 2 == 0 or lane(ln.h, slot) >= 0.65) then
						local open = lane(ln.h, slot) >= 0.9 and slot % 4 == 2
						table.insert(ev, {
							t = t, slot = gslot, kind = ride and "ride" or (open and "hatOpen" or "hat"),
							str = math.clamp(hv, 0.4, 1) * (slot % 4 == 0 and 1 or 0.78), drum = ride and "ride" or "hat",
						})
					end
				end
			end
		end
		if fillList then
			for i, f in fillList do
				local gslot = barBase + f[1]
				local str = 0.62 + 0.38 * (i / #fillList)
				table.insert(ev, {
					t = song.firstBarTime + gslot * slotDur, slot = gslot, kind = f[2] == "snare" and "snare" or "tom",
					str = str, drum = f[2], fill = true,
				})
			end
			-- fill'den sonraki bölüm başı için kick yok: ana vuruşta crash+kick (bir sonraki ölçüde üretilir)
		end
	end
	table.sort(ev, function(a, b)
		if a.t ~= b.t then
			return a.t < b.t
		end
		return a.kind < b.kind
	end)
	-- ── el ataması + FİZİKSEL UYGULANABİLİRLİK ──
	-- Her el için iki vuruş arası en az  t_min = 0.07 + mesafe/hız  sn gerekir (kol hızı sınırlı). Hızlı fill'de eller
	-- dönüşümlü kullanılır; hiçbir elin yetişemeyeceği vuruş atılır (insan zaten çalamaz) - öncelik: crash > tom/snare > ride > hat.
	local ALLOWED = {
		hat = { "Right" }, hatOpen = { "Right" }, ride = { "Right" }, crash = { "Left" },
		snare = { "Left", "Right" }, tom1 = { "Left", "Right" }, tom2 = { "Right", "Left" }, floor = { "Right" },
	}
	local PRIO = { crash = 5, tom = 4, snare = 4, ride = 3, hatOpen = 3, hat = 2 }
	local function drumPos(e: DrumEvent): Vector3
		local name = e.drum == "hatOpen" and "hat" or e.drum
		return DrumKit.PIECES[name].center
	end
	local HAND_SPEED = 7.5 -- stud/sn (referans birim: kit ölçeği)
	local out: { DrumEvent } = {}
	local last: { [string]: { e: DrumEvent, idx: number }? } = { Left = nil, Right = nil }
	for _, e in ev do
		if e.drum == "kick" then
			table.insert(out, e)
		else
			local cand = ALLOWED[e.drum] or { "Left" }
			local best, bestShort = nil, 1e9
			for _, h in cand do
				local l = last[h]
				local short = 0
				if l then
					local need = 0.07 + (drumPos(l.e) - drumPos(e)).Magnitude / HAND_SPEED
					short = math.max(0, need - (e.t - l.e.t))
				end
				if short < bestShort - 1e-9 then
					best, bestShort = h, short
				end
			end
			if bestShort <= 0.02 then
				e.hand = best
				table.insert(out, e)
				last[best] = { e = e, idx = #out }
			else
				-- yetişemiyor: daha öncelikli ise öncekini at, değilse bunu at
				local l = last[best]
				if l and (PRIO[e.kind] or 0) > (PRIO[l.e.kind] or 0) then
					l.e.hand = nil
					l.e.dropped = true
					e.hand = best
					table.insert(out, e)
					last[best] = { e = e, idx = #out }
				end
			end
		end
	end
	local keep: { DrumEvent } = {}
	for _, e in out do
		if not e.dropped then
			table.insert(keep, e)
		end
	end
	return keep
end

-- ───── gitar ─────
-- pc -> (tel, perde): E (6. tel) ve A (5. tel) üzerinde power chord kökü. Önceki konuma en yakın olanı seç.
local function powerChordFret(pc: number, prevFret: number): (number, number)
	local fE = (pc - 4) % 12
	local fA = (pc - 9) % 12
	local candE = { fret = fE, string = 6 }
	local candA = { fret = fA, string = 5 }
	local best = candE
	local function cost(c)
		return math.abs(c.fret - prevFret) + (c.fret > 9 and 3 or 0) + (c.fret == 0 and -0.5 or 0)
	end
	if cost(candA) < cost(candE) then
		best = candA
	end
	return best.fret, best.string
end

local function buildChords(song: any, slotDur: number, barDur: number): { ChordEvent }
	local out: { ChordEvent } = {}
	local prevFret, prevPc = 5, -1
	for h, c in song.chords do
		local pc, q = c[1], c[2]
		if pc ~= prevPc then
			local fret, str = powerChordFret(pc, prevFret)
			local bar = math.floor((h - 1) / 2)
			table.insert(out, {
				t = song.firstBarTime + (h - 1) * barDur / 2, bar = bar, pc = pc, quality = q, fret = fret, string = str,
			})
			prevFret, prevPc = fret, pc
		end
	end
	return out
end

local function buildGuitar(song: any, seed: number, sections: { Section }, slotDur: number): { StrumEvent }
	-- El her zaman 8'lik ızgarada aşağı-yukarı sallanır (gerçek gitaristte kol durmaz); sesli olan ya da
	-- "hayalet" (sessiz) vuruş olarak işaretlenir. Aşağı = vuruş başı, yukarı = "ve". Yön her zaman dönüşümlü.
	local out: { StrumEvent } = {}
	local spb = song.slotsPerBar
	for bar = 0, song.bars - 1 do
		local ln = song.lanes[bar + 1]
		local sec
		for _, s in sections do
			if bar >= s.startBar and bar < s.endBar then
				sec = s
			end
		end
		local kind = sec and sec.kind or "verse"
		local cycle = math.floor(bar / 4) % 4
		for slot = 0, spb - 1, 2 do
			local down = slot % 4 == 0
			local dir = down and 1 or -1
			local g = math.max(lane(ln.g, slot), lane(ln.g, slot + 1) * 0.8)
			local str = 0.4 + 0.6 * g
			local k = down and "down" or "up"
			if slot == 0 then
				str = math.max(str, 0.9)
				k = "accent"
			elseif slot == 8 then
				str = math.max(str, 0.75)
			end
			if g >= 0.8 and slot ~= 0 then
				k = "accent"
			end
			-- yukarı vuruş sakin bölümlerde çoğunlukla hayalet
			local quiet = kind == "intro" or kind == "outro" or kind == "calm"
			if not down and g < (quiet and 0.6 or 0.25) then
				k = "ghost"
				str = 0.2
			end
			if quiet and slot % 8 ~= 0 and g < 0.5 then
				k = "ghost"
				str = 0.2
			end
			-- muted (palm mute) "chug": döngü 3'te vurgusuz vuruşlar
			if kind ~= "chorus" and cycle == 2 and k ~= "accent" and k ~= "ghost" and g < 0.4 then
				k = "mute"
				str = math.min(str, 0.45)
			end
			-- cümle sonunda kısa boşluk: ses kesilir, kol sallanmaya devam eder
			if (bar % 4 == 3) and slot >= 12 and Rng.chance(seed, bar, slot, 0.6) then
				k = "ghost"
				str = 0.2
			end
			table.insert(out, {
				t = song.firstBarTime + (bar * spb + slot) * slotDur, slot = bar * spb + slot,
				dir = dir, str = str, kind = k,
			})
		end
	end
	return out
end

-- ───── bas ─────
local OPEN = { 23, 28, 33, 38, 43 } -- 5 telli: B0 E1 A1 D2 G2

local function snapToChord(midi: number, chordPc: number?): number
	if midi == 0 or chordPc == nil then
		return midi
	end
	-- kök/beşli/oktav perdelerine yakın en yakın nota (±1 yarım ton içinde)
	local allowed = { chordPc, (chordPc + 7) % 12, (chordPc + 3) % 12, (chordPc + 4) % 12 }
	local best, bestD = midi, 99
	for _, pc in allowed do
		for oct = -1, 6 do
			local m = pc + 12 * oct
			local d = math.abs(m - midi)
			if d < bestD then
				best, bestD = m, d
			end
		end
	end
	return bestD <= 1 and best or midi
end

local function bassPosition(midi: number, prevString: number, prevFret: number): (number, number)
	local bestS, bestF, bestCost = 2, 0, 1e9
	for s, open in OPEN do
		local fret = midi - open
		if fret >= 0 and fret <= 12 then
			local cost = math.abs(fret - prevFret) + 0.25 * fret + 0.4 * math.abs(s - prevString) + (fret > 7 and 2 or 0)
			if cost < bestCost then
				bestS, bestF, bestCost = s, fret, cost
			end
		end
	end
	return bestS, bestF
end

local function buildBass(song: any, seed: number, sections: { Section }, slotDur: number): { BassEvent }
	local out: { BassEvent } = {}
	local spb = song.slotsPerBar
	local prevS, prevF = 2, 3
	local finger = 1
	for bar = 0, song.bars - 1 do
		local ln = song.lanes[bar + 1]
		local sec
		for _, s in sections do
			if bar >= s.startBar and bar < s.endBar then
				sec = s
			end
		end
		local kind = sec and sec.kind or "verse"
		local half1, half2 = song.chords[bar * 2 + 1], song.chords[bar * 2 + 2]
		for slot = 0, spb - 1 do
			local beat = math.floor(slot / 4)
			local midiRaw = song.bass[bar * 4 + beat + 1] or 0
			local chord = (slot < 8) and half1 or half2
			local midi = snapToChord(midiRaw, chord and chord[1] or nil)
			if midi > 0 then
				local kv = lane(ln.k, slot)
				local isBeat = slot % 4 == 0
				local eighth = slot % 2 == 0 and (kind == "chorus") and slot % 4 == 2
				local kickLocked = kv >= 0.6 and slot % 2 == 0
				if isBeat or eighth or kickLocked then
					local string, fret = bassPosition(midi, prevS, prevF)
					prevS, prevF = string, fret
					finger = 3 - finger
					local str = isBeat and (slot == 0 and 0.95 or 0.8) or (kickLocked and 0.75 or 0.55)
					table.insert(out, {
						t = song.firstBarTime + (bar * spb + slot) * slotDur, slot = bar * spb + slot, midi = midi,
						str = str, string = string, fret = fret, dur = slotDur * 2, finger = finger,
					})
				end
			end
		end
	end
	-- süreleri bir sonraki notaya kadar uzat (en fazla 1 ölçü)
	for i, e in out do
		local nxt = out[i + 1]
		e.dur = nxt and math.min(nxt.t - e.t, slotDur * 16) or slotDur * 4
	end
	return out
end

-- ───── ölçü stilleri: tekrar hissini kırmak için kontrollü varyasyon ─────
local function buildBarStyles(song: any, seed: number, sections: { Section }): { BarStyle }
	local out: { BarStyle } = {}
	for bar = 0, song.bars - 1 do
		local cycle = math.floor(bar / 4) % 4
		local phase = bar % 4
		local sec
		for _, s in sections do
			if bar >= s.startBar and bar < s.endBar then
				sec = s
			end
		end
		local kind = sec and sec.kind or "verse"
		local sectionLast = sec ~= nil and bar == sec.endBar - 1
		local vocalOn = false
		if kind == "verse" or kind == "calm" then
			vocalOn = phase ~= 3
		elseif kind == "chorus" then
			vocalOn = true
		end
		-- Aynı 4 ölçülük riff her tekrarlandığında kontrollü varyasyon (rastgele değil, döngü numarasına bağlı):
		--   döngü 1: normal sallanma | döngü 2: daha güçlü vurgular, daha çok çökme | döngü 3: kafa hareketi öne çıkar
		--   döngü 4: duruş değişimi (ağırlık, geniş sallanma). Küçük bir (%±8) deterministik oynama tekrarı kırar.
		local jitter = 0.92 + 0.16 * Rng.hash(seed, math.floor(bar / 4), 9)
		local SWAY = { 1.0, 1.1, 0.9, 1.5 }
		local BOUNCE = { 1.0, 1.3, 1.0, 0.9 }
		local LEAN = { 1.0, 1.25, 0.75, 1.1 }
		local HEAD = { 1.0, 1.0, 1.6, 1.2 }
		local ACCENT = { 1.0, 1.3, 1.0, 1.1 }
		table.insert(out, {
			bar = bar, cycle = cycle, phase = phase,
			accentBoost = ACCENT[cycle + 1] * jitter,
			headAmp = HEAD[cycle + 1] * jitter,
			swayMul = SWAY[cycle + 1] * jitter,
			bounceMul = BOUNCE[cycle + 1] * jitter,
			leanMul = LEAN[cycle + 1],
			stanceShift = cycle == 3 and phase == 0, -- döngü 4: duruş değişimi
			fill = sectionLast or (phase == 3 and cycle == 3),
			hold = phase == 3 and Rng.chance(seed, bar, 3, 0.35), -- pose hold: son vuruş sonrası kısa donuk poz
			swayDir = Rng.hash(seed, math.floor(bar / 2), 17) < 0.5 and -1 or 1,
			vocalOn = vocalOn,
		})
	end
	return out
end

function Score.barStyle(self: Score, bar: number): BarStyle
	local i = math.clamp(math.floor(bar), 0, #self.barStyles - 1)
	return self.barStyles[i + 1]
end

function Score.build(song: any, seed: number?): Score
	local sd = seed or 20240601
	local beatDur = 60 / song.bpm
	local barDur = beatDur * song.beatsPerBar
	local slotDur = barDur / song.slotsPerBar
	local sections = buildSections(song, slotDur, barDur)
	local self = {
		song = song, seed = sd, slotDur = slotDur, barDur = barDur, beatDur = beatDur,
		sections = sections,
		drums = buildDrums(song, sd, sections, slotDur),
		guitar = buildGuitar(song, sd, sections, slotDur),
		chords = buildChords(song, slotDur, barDur),
		bass = buildBass(song, sd, sections, slotDur),
		barStyles = buildBarStyles(song, sd, sections),
	}
	return (setmetatable(self, { __index = Score }) :: any) :: Score
end

-- Zamana göre sıralı bir olay listesinde ilk indeks: t >= time (ikili arama)
function Score.firstIndexAtOrAfter(list: { { t: number } }, time: number): number
	local lo, hi = 1, #list + 1
	while lo < hi do
		local mid = (lo + hi) // 2
		if list[mid].t < time then
			lo = mid + 1
		else
			hi = mid
		end
	end
	return lo
end

-- Zaman aralığı (a, b] içindeki olaylar (ardışık karelerde her olay tam bir kez tetiklenir)
function Score.eventsIn(list: { { t: number } }, a: number, b: number): { any }
	local out = {}
	local i = Score.firstIndexAtOrAfter(list, a + 1e-9)
	while i <= #list and list[i].t <= b do
		table.insert(out, list[i])
		i += 1
	end
	return out
end

-- Belirli bir zamandan sonraki n. olay (öngörü / anticipation için)
function Score.nextAfter(list: { { t: number } }, time: number, n: number?): any?
	local i = Score.firstIndexAtOrAfter(list, time + 1e-9) + ((n or 1) - 1)
	return list[i]
end

return Score
]===])
local F_Util = mk(root, "Folder", "Util")
mk(F_Util, "ModuleScript", "Ease", [===[
--!strict
--[[ Zamanlama eğrileri: slow-in/slow-out, kontrollü overshoot, Hermite yayı. Hepsi t∈[0,1] -> [0,1]. ]]

local Ease = {}

function Ease.clamp01(t: number): number
	return math.clamp(t, 0, 1)
end

function Ease.smoothstep(t: number): number
	t = math.clamp(t, 0, 1)
	return t * t * (3 - 2 * t)
end

function Ease.smootherstep(t: number): number
	t = math.clamp(t, 0, 1)
	return t * t * t * (t * (t * 6 - 15) + 10)
end

function Ease.outQuad(t: number): number
	t = math.clamp(t, 0, 1)
	return 1 - (1 - t) * (1 - t)
end

function Ease.inQuad(t: number): number
	t = math.clamp(t, 0, 1)
	return t * t
end

function Ease.inOutCubic(t: number): number
	t = math.clamp(t, 0, 1)
	return t < 0.5 and 4 * t * t * t or 1 - (-2 * t + 2) ^ 3 / 2
end

-- kontrollü overshoot (s ≈ 1.2..2.2): hedefi aşıp geri oturur
function Ease.outBack(t: number, s: number?): number
	t = math.clamp(t, 0, 1)
	local c1 = s or 1.70158
	local c3 = c1 + 1
	return 1 + c3 * (t - 1) ^ 3 + c1 * (t - 1) ^ 2
end

-- Hermite: p0->p1 arası, başlangıç/bitiş hızı (m0, m1; "birim süre başına" değer)
function Ease.hermite(p0: number, m0: number, p1: number, m1: number, t: number): number
	local t2, t3 = t * t, t * t * t
	return (2 * t3 - 3 * t2 + 1) * p0 + (t3 - 2 * t2 + t) * m0 + (-2 * t3 + 3 * t2) * p1 + (t3 - t2) * m1
end

function Ease.lerp(a: number, b: number, t: number): number
	return a + (b - a) * t
end

-- vuruş sonrası sönen titreşim (follow-through): 0 anında 1, sonra sönerek 0'a
function Ease.decayOsc(t: number, freqHz: number, decay: number): number
	if t < 0 then
		return 0
	end
	return math.exp(-decay * t) * math.cos(2 * math.pi * freqHz * t)
end

return Ease
]===])
mk(F_Util, "ModuleScript", "Rng", [===[
--!strict
--[[
	Deterministik, durumsuz rastgelelik: aynı (seed, indeks) her zaman aynı sayıyı verir.
	Amaç gerçek rastgelelik değil, TEKRAR hissini kırmak: her istemcide, her tekrarda aynı performans çıkar
	(sunucu ve istemciler senkron kalır) ve bir ölçüyü geri sarınca aynı varyasyon gelir.
]]

local Rng = {}

local function mix(a: number): number
	a = bit32.bxor(a, bit32.rshift(a, 16))
	a = (a * 0x45d9f3b) % 4294967296
	a = bit32.bxor(a, bit32.rshift(a, 16))
	a = (a * 0x45d9f3b) % 4294967296
	a = bit32.bxor(a, bit32.rshift(a, 16))
	return a
end

-- [0,1)
function Rng.hash(seed: number, a: number, b: number?): number
	local h = mix(seed % 4294967296)
	h = mix(bit32.bxor(h, (a * 2654435761) % 4294967296))
	h = mix(bit32.bxor(h, ((b or 0) * 40503 + 977) % 4294967296))
	return h / 4294967296
end

-- [lo,hi]
function Rng.range(seed: number, a: number, b: number?, lo: number, hi: number): number
	return lo + (hi - lo) * Rng.hash(seed, a, b)
end

-- ağırlıklı/olasılıklı seçim: p olasılıkla true
function Rng.chance(seed: number, a: number, b: number?, p: number): boolean
	return Rng.hash(seed, a, b) < p
end

function Rng.seedFromString(s: string): number
	local h = 2166136261
	for i = 1, #s do
		h = bit32.bxor(h, string.byte(s, i))
		h = (h * 16777619) % 4294967296
	end
	return h
end

return Rng
]===])
mk(F_Util, "ModuleScript", "Spring", [===[
--!strict
--[[
	Kütleli yay (sönümlü harmonik osilatör), kapalı form çözüm: kare süresinden bağımsız, her dt'de kararlı.
	Bir kemiğin hedef poza "kendiliğinden" gecikmeli, hafifçe aşan ve geç oturan şekilde gitmesini sağlar;
	lead & follow ile overlapping action'ı ayrıca gecikme eklemeden üretir.

	freq   : doğal frekans (Hz)         - yüksek = sert/çevik, düşük = gevşek/ağır
	damping: sönüm oranı ζ               - 1 = kritik, <1 = aşar (overshoot), >1 = ağır sönüm
]]

local Spring = {}
Spring.__index = Spring

export type Spring = typeof(setmetatable({} :: { x: number, v: number, freq: number, damping: number }, Spring))

function Spring.new(x: number, freq: number, damping: number): Spring
	return setmetatable({ x = x, v = 0, freq = freq, damping = damping }, Spring)
end

-- tek adım: (konum, hız) döndürür
local function advance(x: number, v: number, target: number, freq: number, zeta: number, dt: number): (number, number)
	if dt <= 0 then
		return x, v
	end
	local omega = freq * 2 * math.pi
	local c1 = x - target
	if zeta > 1.0001 then
		local zb = omega * math.sqrt(zeta * zeta - 1)
		local za = -omega * zeta
		local z1, z2 = za - zb, za + zb
		local B = (v - z1 * c1) / (z2 - z1)
		local A = c1 - B
		local e1, e2 = math.exp(z1 * dt), math.exp(z2 * dt)
		return target + A * e1 + B * e2, A * z1 * e1 + B * z2 * e2
	elseif zeta < 0.9999 then
		local oz = omega * zeta
		local alpha = omega * math.sqrt(1 - zeta * zeta)
		local c2 = (v + oz * c1) / alpha
		local e = math.exp(-oz * dt)
		local cs, sn = math.cos(alpha * dt), math.sin(alpha * dt)
		local pos = e * (c1 * cs + c2 * sn)
		local vel = e * (-oz * (c1 * cs + c2 * sn) + alpha * (c2 * cs - c1 * sn))
		return target + pos, vel
	else
		local e = math.exp(-omega * dt)
		local c2 = v + omega * c1
		return target + (c1 + c2 * dt) * e, (v - c2 * omega * dt) * e
	end
end

function Spring.step(self: Spring, target: number, dt: number): number
	self.x, self.v = advance(self.x, self.v, target, self.freq, self.damping, dt)
	return self.x
end

-- hıza ani katkı (vuruş tepkisi): v += dv
function Spring.impulse(self: Spring, dv: number)
	self.v += dv
end

-- Hıza, ilk tepe genliği tam `amp` olacak şekilde katkı yap (sanatçı dostu: "0.07 stud çökme").
-- Gerçek dünya karşılığı: vuruşta bir kütleye verilen darbe; sonrası yayın kendi aşma/oturma davranışı.
function Spring.impulseForPeak(self: Spring, amp: number)
	local omega = self.freq * 2 * math.pi
	local z = self.damping
	local peakPerV: number -- tepe = v0 * peakPerV
	if z < 0.9999 then
		local s = math.sqrt(1 - z * z)
		peakPerV = math.exp(-(z / s) * math.atan2(s, z)) / omega
	elseif z <= 1.0001 then
		peakPerV = 1 / (omega * math.exp(1))
	else
		local s = math.sqrt(z * z - 1)
		local z1, z2 = -omega * (z + s), -omega * (z - s) -- kökler
		local tp = math.log(z1 / z2) / (z2 - z1)
		peakPerV = (math.exp(z2 * tp) - math.exp(z1 * tp)) / (z2 - z1)
	end
	self.v += amp / peakPerV
end

function Spring.reset(self: Spring, x: number)
	self.x, self.v = x, 0
end

-- Üç eksenli yay (Vector3 değer)
local Spring3 = {}
Spring3.__index = Spring3

export type Spring3 = typeof(setmetatable({} :: { x: Spring, y: Spring, z: Spring }, Spring3))

function Spring3.new(value: Vector3, freq: number, damping: number): Spring3
	return setmetatable({
		x = Spring.new(value.X, freq, damping),
		y = Spring.new(value.Y, freq, damping),
		z = Spring.new(value.Z, freq, damping),
	}, Spring3)
end

function Spring3.step(self: Spring3, target: Vector3, dt: number): Vector3
	return Vector3.new(self.x:step(target.X, dt), self.y:step(target.Y, dt), self.z:step(target.Z, dt))
end

function Spring3.get(self: Spring3): Vector3
	return Vector3.new(self.x.x, self.y.x, self.z.x)
end

function Spring3.impulse(self: Spring3, dv: Vector3)
	self.x.v += dv.X
	self.y.v += dv.Y
	self.z.v += dv.Z
end

function Spring3.impulseForPeak(self: Spring3, amp: Vector3)
	if amp.X ~= 0 then self.x:impulseForPeak(amp.X) end
	if amp.Y ~= 0 then self.y:impulseForPeak(amp.Y) end
	if amp.Z ~= 0 then self.z:impulseForPeak(amp.Z) end
end

function Spring3.reset(self: Spring3, value: Vector3)
	self.x:reset(value.X)
	self.y:reset(value.Y)
	self.z:reset(value.Z)
end

function Spring3.setParams(self: Spring3, freq: number, damping: number)
	for _, s in { self.x, self.y, self.z } do
		s.freq, s.damping = freq, damping
	end
end

return {
	Spring = Spring,
	Spring3 = Spring3,
	advance = advance,
}
]===])
local F_Layers = mk(root, "Folder", "Layers")
mk(F_Layers, "ModuleScript", "Base", [===[
--!strict
--[[
	TEMEL KATMAN: nefes, duruş (stance), ayak planı ve dengelenme.
	Her zaman çalışır (müzik yokken de karakter donuk durmaz). Ayaklar yere SABİT: kalça kayınca bacaklar IK ile
	gerçekten uyum sağlar (ayak kaymaz); ağırlık aktarımında yüksüz ayağın topuğu hafifçe kalkar ve ritimde vurur.
]]

local Root = script:FindFirstAncestor("BandPerformance")
local Config = require(Root.Config)
local Ease = require(Root.Util.Ease)

local Base = {}
Base.__index = Base

function Base.new(perf: any)
	return setmetatable({ name = "Base", phase = 0, breathPhase = 0, tap = { Left = 0, Right = 0 } }, Base)
end

local function up(v: number): number
	return v
end

function Base.prepare(self: any, perf: any, ctx: any, pose: any)
	local dt = ctx.dt
	local P = perf.profile
	local sw = ctx.sw
	-- ── nefes: dinlenmede yavaş-derin, performansta sığ-hızlı; Ready'de derin hazırlık nefesi
	local rate = 0.22 + 0.5 * ctx.groove
	self.breathPhase += dt * 2 * math.pi * rate
	local breath = math.sin(self.breathPhase)
	local depth = (1 - 0.6 * ctx.playW) + 0.8 * sw.Ready
	pose:addEuler("Waist", Vector3.new(breath * Config.deg(1.1) * depth, 0, 0))
	pose:addShoulder("Left", Vector3.new(0, breath * 0.018 * depth, 0))
	pose:addShoulder("Right", Vector3.new(0, breath * 0.018 * depth, 0))
	pose:addEuler("Neck", Vector3.new(-breath * Config.deg(0.5) * depth, 0, 0))

	-- ── Ready: hazırlık, hafif geri yaslanıp gövdeyi toplama (anticipation)
	if sw.Ready > 0.01 then
		pose:addEuler("Waist", Vector3.new(-Config.deg(3.5), 0, 0), sw.Ready)
	end
	-- ── Recovery: omuzlar düşer, ağır nefes verme
	if sw.Recovery > 0.01 then
		pose:addShoulder("Left", Vector3.new(0, -0.05, 0.02), sw.Recovery)
		pose:addShoulder("Right", Vector3.new(0, -0.05, 0.02), sw.Recovery)
		pose:addEuler("Waist", Vector3.new(Config.deg(4), 0, 0), sw.Recovery)
	end
	-- ── Outro: gövde gevşer, kafa hafif öne
	if sw.Outro > 0.01 then
		pose:addEuler("Neck", Vector3.new(Config.deg(8), 0, 0), sw.Outro)
		pose:addEuler("Waist", Vector3.new(Config.deg(3), 0, 0), sw.Outro)
	end
	-- stance: dizler hafif bükülü (tam düz bacak IK tekilliği + robotik durur); performansta biraz daha çökük
	if not perf.seated then
		local legLen = perf.rig.lengths.legUpper + perf.rig.lengths.legLower
		pose:addRoot(Vector3.new(0, -legLen * (0.05 + 0.025 * ctx.playW), 0))
	end
	-- stance: duruşta hafif öne eğik (performans pozu); profil.lean
	pose:addEuler("Waist", Vector3.new(P.lean * 0.5 * (0.4 + 0.6 * ctx.playW), 0, 0))
end

-- Ayak planı: dinlenme ayak konumları + duruş genişliği/açısı + ağırlık aktarımı + ritimde ayak vuruşu
function Base.contact(self: any, perf: any, ctx: any, pose: any)
	if perf.seated then
		return
	end
	local P = perf.profile
	local dyn = perf.dyn
	local shiftX = dyn.pelvisShift.x.x -- + = ağırlık sağ ayakta
	local amp = math.max(P.sway, 0.001)
	local loadRight = math.clamp(shiftX / amp, -1, 1)
	local stage = perf.rig.rootCF
	local sideVec = stage:VectorToWorldSpace(Vector3.new(1, 0, 0))
	for _, side in { "Right", "Left" } do
		local sgn = side == "Right" and 1 or -1
		local ankle = perf.rest.ankle[side]
		-- genişlik
		ankle += sideVec * ((P.stanceWidth - 1) * 0.5 * sgn)
		-- ayak açısı (parmaklar dışa)
		local yaw = P.stanceYaw * sgn * -1
		local rot = CFrame.Angles(0, yaw, 0) * perf.rest.footRot[side]
		-- yüksüz ayak: ağırlık karşı ayakta (loadRight * sgn < 0) -> topuk kalkar
		local unloaded = math.clamp(-loadRight * sgn, 0, 1)
		local lift = 0.035 * unloaded
		local pitch = Config.deg(5) * unloaded
		-- ritimde ayak vuruşu (yalnızca yüksüz ayak, enerjiyle)
		local tapAmp = P.footTap * ctx.groove * unloaded
		if tapAmp > 0.01 then
			local frac = ctx.beatFloat % 1
			local h = Ease.smoothstep((frac - 0.45) / 0.55) -- vuruşa doğru yükselir, vuruşta düşer
			lift += 0.07 * tapAmp * h
			pitch += Config.deg(14) * tapAmp * h
		end
		local worldUp = Vector3.new(0, 1, 0)
		pose:setFoot(side, {
			ankle = ankle + worldUp * lift,
			rot = stage.Rotation * CFrame.Angles(-pitch, 0, 0) * stage.Rotation:Inverse() * rot,
			w = 1,
		})
	end
end

return Base
]===])
mk(F_Layers, "ModuleScript", "Follow", [===[
--!strict
--[[
	Gövdeye bağlı rijit nesnenin (gitar, mikrofon, davul çubuğu...) FOLLOW-THROUGH'u.
	Ebeveyn (torso) hareket edince nesne ilk anda "geride kalır", sonra yayla yetişip hafifçe aşar, oturur.
	Yöntem: ebeveynin kare-kare dönüşünü ve ötelemesini ters işaretle yaya ekle (nesne ilk anda olduğu yerde
	kalmaya çalışır), yay sıfıra çeker. Ani poz değişiminde nesne tamamen sabit KALMAZ ama sekmez de.
]]

local Root = script:FindFirstAncestor("BandPerformance")
local SpringM = require(Root.Util.Spring)
local Spring3 = SpringM.Spring3

local Follow = {}
Follow.__index = Follow

function Follow.new(freq: number, damping: number, rotGain: number?, posGain: number?)
	return setmetatable({
		rot = Spring3.new(Vector3.zero, freq, damping),
		pos = Spring3.new(Vector3.zero, freq, damping),
		prev = nil :: CFrame?,
		rotGain = rotGain or 0.7,
		posGain = posGain or 0.6,
	}, Follow)
end

function Follow.reset(self: any)
	self.prev = nil
	self.rot:reset(Vector3.zero)
	self.pos:reset(Vector3.zero)
end

-- parent: ebeveynin bu karedeki DÜNYA CFrame'i. Dönüş: ebeveyn uzayında (pos, rot) ofseti CFrame
function Follow.step(self: any, parent: CFrame, dt: number): CFrame
	local prev = self.prev
	if prev then
		-- ebeveyn uzayında kare-kare dönüş ve öteleme
		local d = prev:Inverse() * parent
		local axis, ang = d:ToAxisAngle()
		if ang > 1e-6 then
			local rv = axis * ang
			self.rot.x.x -= rv.X * self.rotGain
			self.rot.y.x -= rv.Y * self.rotGain
			self.rot.z.x -= rv.Z * self.rotGain
		end
		local dp = d.Position
		self.pos.x.x -= dp.X * self.posGain
		self.pos.y.x -= dp.Y * self.posGain
		self.pos.z.x -= dp.Z * self.posGain
	end
	self.prev = parent
	local r = self.rot:step(Vector3.zero, dt)
	local p = self.pos:step(Vector3.zero, dt)
	-- sınırlı: kontrolsüz titreşimi engelle
	r = Vector3.new(math.clamp(r.X, -0.35, 0.35), math.clamp(r.Y, -0.35, 0.35), math.clamp(r.Z, -0.35, 0.35))
	return CFrame.new(p) * CFrame.Angles(r.X, r.Y, r.Z)
end

-- vuruşta nesneye dışarıdan darbe (ör. gitar kendine çekilir): pos darbesi (stud tepe) ve rot (rad tepe)
function Follow.kick(self: any, posPeak: Vector3?, rotPeak: Vector3?)
	if posPeak then
		self.pos:impulseForPeak(posPeak)
	end
	if rotPeak then
		self.rot:impulseForPeak(rotPeak)
	end
end

return Follow
]===])
mk(F_Layers, "ModuleScript", "Groove", [===[
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
	local calm = perf.calm:step(perf.calmTarget, dt)
	g *= (1 - 0.55 * calm) -- sustain'de gövde sakinleşir

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
			perf:kick(t + bd, dyn.pelvisY, -P.bounce * str * style.bounceMul)
		end
		perf:kick(t + bd + 0.025, dyn.waist.x, P.nod * 0.45 * str)
		perf:kick(t + bd + 0.05, dyn.neck.x, P.nod * str * headAmp)
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
	local amp = P.sway * (0.35 + 0.65 * g) * style.swayMul
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
	local waistTarget = Vector3.new(P.lean * 0.4 * g * style.leanMul + bias.waistPitch, bias.waistYaw, -pr.Z * P.chestCounter)
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
]===])
mk(F_Layers, "ModuleScript", "Interaction", [===[
--!strict
--[[
	Etkileşim katmanı: biriken pozdaki el/ayak hedeflerini IK ile çözüp eklem Transform'larına yazar.
	FK (katmanların dönüşleri) ile IK arasında ağırlıkla karıştırır; ağırlık yayla yumuşatılır (snap yok).
	Ayrıca temas hatasını (hedef - gerçek) ölçer: perf.metrics.
]]

local Root = script:FindFirstAncestor("BandPerformance")
local IK = require(Root.Rig.TwoBoneIK)
local Config = require(Root.Config)

local Interaction = {}

local I = CFrame.identity
local SIDES = { "Right", "Left" }

--[[
	Uç noktayı (parmak ucu / ayak bileği) SABİT tutup bilek açısını sınırın içinde bırakır:
	sınır aşılırsa el yönelimi gevşetilir (hedef yönelimden sapar) ama TEMAS NOKTASI kaymaz.
	endPos(handRot) uç parçanın konumunu verir (kavrama ofseti dönmeyle değişir).
]]
local function solveRelaxed(parent: CFrame, j1: any, j2: any, j3: any, rot0: CFrame, endPos: (CFrame) -> Vector3, pole: Vector3, flex: number, soft: number, off: Vector3?, limit: number, roll: number?)
	local rot = rot0
	local res
	for _ = 1, 3 do
		local endCF = CFrame.new(endPos(rot)) * rot
		res = IK.solveChain(parent, j1, j2, j3, endCF, pole, flex, soft, off, roll)
		local axis, ang = res.t3:ToAxisAngle()
		if ang <= limit + 1e-4 then
			return res, res.t3
		end
		local t3c = CFrame.fromAxisAngle(axis, limit)
		local Fw = res.cf2 * j3.c0
		rot = (Fw * t3c * j3.c1:Inverse()).Rotation
	end
	-- son çözüm: gevşetilmiş yönelimle
	local endCF = CFrame.new(endPos(rot)) * rot
	res = IK.solveChain(parent, j1, j2, j3, endCF, pole, flex, soft, off, roll)
	return res, IK.limitRotation(res.t3, limit)
end

local function blend(fk: CFrame?, ik: CFrame, w: number): CFrame
	local f = fk or I
	if w >= 0.999 then
		return ik
	end
	return f:Lerp(ik, w)
end

-- tr: eklem adı -> Transform (iskelet katmanları zaten yazılmış), parts: o ana kadarki FK dünya CFrame'leri
function Interaction.solve(perf: any, pose: any, tr: { [string]: CFrame }, parts: { [string]: CFrame }, dt: number)
	local rig = perf.rig
	local lim = Config.limits
	local metrics = perf.metrics

	-- kollar
	for _, side in SIDES do
		local sh, el, wr = side .. "Shoulder", side .. "Elbow", side .. "Wrist"
		local h = pose.hands[side]
		local w = perf.ikSpring[side]:step(h and h.w or 0, dt)
		w = math.clamp(w, 0, 1)
		local off = pose.shoulder[side]
		local fk1, fk2, fk3 = pose.rot[sh], pose.rot[el], pose.rot[wr]
		if h and w > 0.002 then
			local ut = parts.UpperTorso
			local outward = side == "Right" and 1 or -1
			local pole = h.pole or ut:VectorToWorldSpace(Vector3.new(0.55 * outward, -0.8, 0.35))
			if h.elbowOpen and h.elbowOpen ~= 0 then
				pole += ut:VectorToWorldSpace(Vector3.new(outward, 0, 0)) * (h.elbowOpen * 2)
			end
			local handRot0 = (h.cf * h.grip:Inverse()).Rotation
			local tipPos = h.cf.Position
			local gripPos = h.grip.Position
			local res, t3 = solveRelaxed(ut, rig:info(sh), rig:info(el), rig:info(wr), handRot0,
				function(r) return tipPos - r:VectorToWorldSpace(gripPos) end, pole, 1, rig.lengths.reach * 0.06, off, lim.wrist, 0.65)
			tr[sh] = blend(fk1, res.t1, w)
			tr[el] = blend(fk2, res.t2, w)
			tr[wr] = blend(fk3, t3, w)
			metrics.reach[side] = res.reachError
		else
			tr[sh] = CFrame.new(off) * (fk1 or I)
			tr[el] = fk2 or I
			tr[wr] = fk3 or I
			metrics.reach[side] = 0
		end
	end

	-- bacaklar
	for _, side in SIDES do
		local hip, knee, ank = side .. "Hip", side .. "Knee", side .. "Ankle"
		local f = pose.feet[side]
		if f and f.w > 0.002 then
			local lt = parts.LowerTorso
			local out = side == "Right" and 1 or -1
			local c1p = rig.joints[ank].c1.Position
			local pole = f.pole or lt:VectorToWorldSpace(Vector3.new(0.18 * out, 0, -1))
			local res, t3 = solveRelaxed(lt, rig:info(hip), rig:info(knee), rig:info(ank), f.rot,
				function(r) return f.ankle - r:VectorToWorldSpace(c1p) end, pole, -1, rig.lengths.legUpper * 0.04, nil, lim.ankle)
			local w = math.clamp(f.w, 0, 1)
			tr[hip] = blend(pose.rot[hip], res.t1, w)
			tr[knee] = blend(pose.rot[knee], res.t2, w)
			tr[ank] = blend(pose.rot[ank], t3, w)
			metrics.reach[side .. "Foot"] = res.reachError
		else
			tr[hip] = pose.rot[hip] or I
			tr[knee] = pose.rot[knee] or I
			tr[ank] = pose.rot[ank] or I
			metrics.reach[side .. "Foot"] = 0
		end
	end
end

return Interaction
]===])
mk(F_Layers, "ModuleScript", "Pose", [===[
--!strict
--[[
	Karelik poz biriktirici. Her katman buraya KATKI yapar; hiçbiri rig'i doğrudan yazmaz.
	Karıştırma kuralları:
	  - eklem dönüşleri: sırayla çarpılır, her biri ağırlıkla (w) kimlikten kısılır  =>  r = r * identity:Lerp(d, w)
	  - kök ofseti/dönüşü, omuz kayması: ağırlıklı toplama
	  - el/ayak hedefleri: ağırlıklı geçiş (daha sonra gelen katman, w kadar önceki hedefi ezer)
	Böylece "tüm karakteri tek track ile kilitlemek" yerine bağımsız, ağırlıklı katmanlar elde edilir ve
	bir katmanın kapanması (w -> 0) poz atlaması yapmaz.
]]

export type HandTarget = {
	cf: CFrame, -- tutuş çerçevesinin (grip) istenen DÜNYA CFrame'i
	grip: CFrame, -- Hand parçasına göre tutuş çerçevesi (parmak ucu/çubuk tutuşu)
	w: number, -- 0..1 ne kadar IK
	pole: Vector3?, -- dirsek yönü (dünya)
	elbowOpen: number?, -- dirseği dışa aç (stud)
}

export type FootTarget = {
	ankle: Vector3, -- ayak bileği ekleminin DÜNYA konumu
	rot: CFrame, -- ayak parçasının DÜNYA yönelimi (saf dönüş)
	w: number,
	pole: Vector3?,
}

export type Pose = {
	rot: { [string]: CFrame },
	rootOffset: Vector3,
	rootRot: CFrame,
	shoulder: { Left: Vector3, Right: Vector3 }, -- UpperTorso uzayında omuz (klavikula) kayması
	hands: { Left: HandTarget?, Right: HandTarget? },
	feet: { Left: FootTarget?, Right: FootTarget? },
	gaze: Vector3, -- (pitch, yaw, roll) bakış ek açıları (kafa)
}

local Pose = {}
Pose.__index = Pose

function Pose.new(): Pose
	return setmetatable({
		rot = {},
		rootOffset = Vector3.zero,
		rootRot = CFrame.identity,
		shoulder = { Left = Vector3.zero, Right = Vector3.zero },
		hands = {},
		feet = {},
		gaze = Vector3.zero,
	}, Pose) :: any
end

function Pose.addRot(self: Pose, joint: string, delta: CFrame, w: number?)
	local weight = w or 1
	if weight <= 0 then
		return
	end
	local d = weight >= 1 and delta or CFrame.identity:Lerp(delta, weight)
	local cur = self.rot[joint]
	self.rot[joint] = cur and (cur * d) or d
end

--[[
	ANLAMSAL euler (katmanlar bu dili konuşur): x = öne eğilme/öne selam (+ = burun aşağı), y = sola dönüş (+),
	z = sola yatış (+: sağ omuz/kalça yukarı). Roblox'ta +X dönüşü gövdeyi GERİYE yatırır, bu yüzden x işaret değiştirir.
]]
function Pose.angles(v: Vector3): CFrame
	return CFrame.Angles(-v.X, v.Y, v.Z)
end

function Pose.addEuler(self: Pose, joint: string, v: Vector3, w: number?)
	Pose.addRot(self, joint, Pose.angles(v), w)
end

function Pose.addRoot(self: Pose, offset: Vector3, rot: CFrame?, w: number?)
	local weight = w or 1
	self.rootOffset += offset * weight
	if rot then
		self.rootRot = self.rootRot * (weight >= 1 and rot or CFrame.identity:Lerp(rot, weight))
	end
end

function Pose.addShoulder(self: Pose, side: string, offset: Vector3, w: number?)
	local weight = w or 1
	if side == "Left" then
		self.shoulder.Left += offset * weight
	else
		self.shoulder.Right += offset * weight
	end
end

function Pose.setHand(self: Pose, side: string, tgt: HandTarget)
	local hands: any = self.hands
	local prev = hands[side] :: HandTarget?
	if prev and tgt.w < 1 then
		local w = tgt.w
		local merged: HandTarget = {
			cf = prev.cf:Lerp(tgt.cf, w),
			grip = prev.grip:Lerp(tgt.grip, w),
			w = prev.w + (1 - prev.w) * w,
			pole = tgt.pole or prev.pole,
			elbowOpen = (prev.elbowOpen or 0) + ((tgt.elbowOpen or 0) - (prev.elbowOpen or 0)) * w,
		}
		hands[side] = merged
	else
		hands[side] = tgt
	end
end

function Pose.setFoot(self: Pose, side: string, tgt: FootTarget)
	local feet: any = self.feet
	local prev = feet[side] :: FootTarget?
	if prev and tgt.w < 1 then
		local w = tgt.w
		feet[side] = {
			ankle = prev.ankle:Lerp(tgt.ankle, w),
			rot = prev.rot:Lerp(tgt.rot, w),
			w = prev.w + (1 - prev.w) * w,
			pole = tgt.pole or prev.pole,
		}
	else
		feet[side] = tgt
	end
end

return Pose
]===])
mk(F_Layers, "ModuleScript", "Strum", [===[
--!strict
--[[
	Strum/vuruş eğrisi: sağ elin sürekli sallanması. Aşağı-yukarı ardışık "geçişler" (iplerin düzlemini
	kesme anları = ses anı) arasında Hermite eğrisi. Her geçişteki hız, o vuruşun şiddetinden gelir:
	  - şiddetli vuruşa giden salınım daha YÜKSEK kalkar (anticipation kendiliğinden)
	  - hayalet vuruşta kol küçük ama sürekli hareket eder (sesli/sessiz fark yok, el durmaz)
	  - uzun boşlukta salınım söner, el ipler üzerinde bekler
	Dönüş s ∈ [-1..1]: +1 = aşağı vuruşun en uzak noktası, 0 = ip düzlemi (ses anı).
	Konum ve hız süreklidir (Hermite, uç hızları komşu vuruşlarla eşleşir).
]]

local Root = script:FindFirstAncestor("BandPerformance")
local Score = require(Root.Music.Score)

local Strum = {}

local AMP = { accent = 1.0, down = 0.8, up = 0.7, mute = 0.45, ghost = 0.38 }

local function amp(e: any, gap: number): number
	local a = AMP[e.kind] or 0.7
	a = a * (0.7 + 0.3 * e.str)
	-- uzun boşluk: salınım söner
	local fade = 1 - 0.55 * math.clamp((gap - 0.35) / 0.65, 0, 1)
	return a * fade
end

--[[ strums: zamana sıralı olay listesi (Score.guitar). t: şu an. Dönüş: s, ds/dt(1/sn), prevEvent, nextEvent, u(0..1) ]]
function Strum.eval(strums: { any }, t: number): (number, number, any?, any?, number)
	local i = Score.firstIndexAtOrAfter(strums, t + 1e-9) - 1 -- t_k <= t
	local a, b = strums[i], strums[i + 1]
	if a == nil or b == nil then
		return 0, 0, a, b, 0
	end
	local T = b.t - a.t
	local u = (t - a.t) / T
	local nxt = strums[i + 2]
	local prv = strums[i - 1]
	local Aa = amp(a, prv and (a.t - prv.t) or T)
	local Ab = amp(b, nxt and (nxt.t - b.t) or T)
	-- aşağı vuruş (dir=+1) a'dan b'ye: konum = dir * 4 * [Aa u(1-u)² + Ab u²(1-u)]
	local u1 = 1 - u
	local p = a.dir * 4 * (Aa * u * u1 * u1 + Ab * u * u * u1)
	local dp = a.dir * 4 * (Aa * (u1 * u1 - 2 * u * u1) + Ab * (2 * u * u1 - u * u)) / T
	-- normalize: genlik 1 ≈ tepe (4*A/4 = A)
	return p, dp, a, b, u
end

return Strum
]===])
local F_Performers = mk(root, "Folder", "Performers")
mk(F_Performers, "ModuleScript", "Bassist", [===[
--!strict
--[[ Basçı: Performer + Stringed("Bass"). Gitardan farklı: ağır groove, parmak pluck, sakin sağ el. ]]

local Root = script:FindFirstAncestor("BandPerformance")
local Performer = require(Root.Performers.Performer)
local Stringed = require(Root.Performers.Stringed)

local Bassist = {}

function Bassist.create(rig: any, opts: { score: any, clock: any, seed: number? })
	return Performer.new(rig, "Bass", {
		score = opts.score, clock = opts.clock, seed = opts.seed,
		instrument = function(perf)
			return Stringed.new(perf, "Bass")
		end,
	})
end

return Bassist
]===])
mk(F_Performers, "ModuleScript", "DrumKit", [===[
--!strict
--[[
	Davul seti yerleşimi. Konumlar OTURAN KALÇA merkezine (LowerTorso, oturuş pozunda) göre ve referans erişim 2.2
	stud için yazıldı; rig'in erişimine göre ölçeklenir. +X davulcunun sağı, -Z ileri (set önde).
	Hem animasyon (hedefler) hem PropBuilder (parçalar) aynı tabloyu kullanır -> el ile set hep hizalı.
]]

local DrumKit: any = {}

export type Piece = {
	name: string,
	kind: string, -- "head" (derili davul) | "cymbal" | "kick" | "hat"
	center: Vector3, -- kalça merkezine göre, referans birim
	radius: number,
	tilt: number, -- yüzey normalinin davulcuya doğru eğimi (rad)
	thickness: number,
}

-- tilt: +: yüzey davulcuya doğru yatık (normal = (0, cos, +sin)), teller/zil hafif eğik
DrumKit.PIECES = {
	snare = { kind = "head", center = Vector3.new(0.00, 0.62, -1.9), radius = 0.42, tilt = math.rad(6), thickness = 0.28 },
	tom1 = { kind = "head", center = Vector3.new(-0.45, 1.0, -2.3), radius = 0.34, tilt = math.rad(24), thickness = 0.3 },
	tom2 = { kind = "head", center = Vector3.new(0.5, 1.0, -2.3), radius = 0.37, tilt = math.rad(22), thickness = 0.32 },
	floor = { kind = "head", center = Vector3.new(1.55, 0.4, -2.05), radius = 0.5, tilt = math.rad(4), thickness = 0.55 },
	hat = { kind = "hat", center = Vector3.new(-1.0, 0.95, -1.7), radius = 0.4, tilt = math.rad(6), thickness = 0.06 },
	crash = { kind = "cymbal", center = Vector3.new(-1.75, 1.55, -2.7), radius = 0.55, tilt = math.rad(18), thickness = 0.05 },
	ride = { kind = "cymbal", center = Vector3.new(1.95, 1.3, -2.6), radius = 0.62, tilt = math.rad(12), thickness = 0.05 },
	kick = { kind = "kick", center = Vector3.new(0.12, 0.35, -3.0), radius = 0.8, tilt = 0, thickness = 0.9 },
}

-- ayak pedalları (ayak bileği hedef konumu, kalça merkezine göre): sağ = kick pedalı, sol = hi-hat pedalı
DrumKit.PEDALS = {
	Right = Vector3.new(0.38, -1.34, -1.55),
	Left = Vector3.new(-0.72, -1.38, -1.25),
}

--[[ rig + sahne CFrame'i (HRP) için dünya yerleşimi. seatDrop: kalçanın dinlenme duruşuna göre alçalması (üst bacak boyu)
	Dönüş: parça adı -> { pos, normal, radius, kind, up(rel) }, pedallar, orijin (oturan kalça merkezi) ]]
function DrumKit.layout(rig: any, stage: CFrame)
	local s = rig.lengths.reach / 2.2
	local seatDrop = rig.lengths.legUpper
	-- dinlenme duruşunda kalça merkezi = HRP (LowerTorso) kök; otururken seatDrop kadar aşağıda
	local lt = rig.joints.Root
	local origin = stage * lt.c0 * Vector3.new(0, -seatDrop, 0)
	local out = {}
	for name, p in pairs(DrumKit.PIECES :: { [string]: any }) do
		local c = stage:VectorToWorldSpace(p.center * s) + origin
		local n = stage:VectorToWorldSpace(Vector3.new(0, math.cos(p.tilt), math.sin(p.tilt)))
		out[name] = { name = name, kind = p.kind, pos = c, normal = n, radius = p.radius * s, thickness = p.thickness * s, tilt = p.tilt }
	end
	local pedals = {}
	for side, v in pairs(DrumKit.PEDALS :: { [string]: Vector3 }) do
		pedals[side] = stage:VectorToWorldSpace(v * s) + origin
	end
	return { pieces = out, pedals = pedals, origin = origin, scale = s, seatDrop = seatDrop }
end

return DrumKit
]===])
mk(F_Performers, "ModuleScript", "Drummer", [===[
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
]===])
mk(F_Performers, "ModuleScript", "Guitarist", [===[
--!strict
--[[ Gitarist: Performer + Stringed("Guitar"). Fabrika: Guitarist.create(rig, {score, clock, seed}) ]]

local Root = script:FindFirstAncestor("BandPerformance")
local Performer = require(Root.Performers.Performer)
local Stringed = require(Root.Performers.Stringed)

local Guitarist = {}

function Guitarist.create(rig: any, opts: { score: any, clock: any, seed: number? })
	return Performer.new(rig, "Guitar", {
		score = opts.score, clock = opts.clock, seed = opts.seed,
		instrument = function(perf)
			return Stringed.new(perf, "Guitar")
		end,
	})
end

return Guitarist
]===])
mk(F_Performers, "ModuleScript", "Performer", [===[
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
]===])
mk(F_Performers, "ModuleScript", "PerformerState", [===[
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
]===])
mk(F_Performers, "ModuleScript", "Stringed", [===[
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
]===])
mk(F_Performers, "ModuleScript", "Vocalist", [===[
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
]===])
local F_Props = mk(root, "Folder", "Props")
mk(F_Props, "ModuleScript", "PropBuilder", [===[
--!strict
--[[
	Prosedürel enstrüman/prop üretimi + her karede animasyona bağlama. Props anchored ve yalnızca İSTEMCİDE
	CFrame ile sürülür (karakterin Motor6D animasyonuyla aynı karede, replikasyonsuz, gecikmesiz).

	Kendi modellerini kullanmak istersen: model adını "<Rol>_Prop" ver (ör. Guitar_Prop) ve karakter modelinin içine koy;
	PrimaryPart'ı "enstrüman çerçevesi" olmalı (gitar/bas: gövde merkezi, +X başlığa, +Z yüzeyden dışarı, +Y üst kenar).
	Bu durumda hiçbir parça üretilmez; yalnızca model her kare bu çerçeveye taşınır (adopt).
]]

local Root = script:FindFirstAncestor("BandPerformance")
local DrumKit = require(Root.Performers.DrumKit)

local PropBuilder = {}

local function part(parent: any, name: string, size: Vector3, color: Color3, shape: any?, material: any?): any
	local p = Instance.new("Part")
	p.Name = name
	p.Size = size
	p.Color = color
	p.Anchored = true
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.Massless = true
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	if shape then
		p.Shape = shape
	end
	if material then
		p.Material = material
	end
	p.Parent = parent
	return p
end

-- silindirin ekseni (Roblox'ta X) normal yönüne hizalı CFrame
local function cylinderCF(center: Vector3, normal: Vector3): CFrame
	local up = math.abs(normal.Y) < 0.95 and Vector3.new(0, 1, 0) or Vector3.new(1, 0, 0)
	local y = up:Cross(normal).Unit
	local z = normal:Cross(y)
	return CFrame.fromMatrix(center, normal, y, z)
end

local function c3(r: number, g: number, b: number): Color3
	return Color3.fromRGB(r, g, b)
end

export type Prop = {
	instances: { any },
	update: (Prop, any, any, any) -> (),
	destroy: (Prop) -> (),
}

local function newProp(model: any): any
	return {
		model = model,
		parts = {} :: { { part: any, off: CFrame } }, -- sabit ofsetli parçalar (enstrüman çerçevesine göre)
		update = function() end,
		destroy = function(self: any)
			model:Destroy()
		end,
	}
end

-- ─────────── gitar / bas ───────────
local function buildStringed(kind: string, perf: any, parent: any): any
	local layer = perf.instrument
	local spec, s = layer.spec, layer.s
	local isBass = kind == "Bass"
	local model = Instance.new("Model")
	model.Name = kind .. "_Prop"
	model.Parent = parent
	local prop = newProp(model)

	local bodyL, bodyW = (isBass and 0.95 or 0.85) * s, (isBass and 0.62 or 0.58) * s
	local thick = 0.30 * s
	local body = part(model, "Body", Vector3.new(bodyL * 2, bodyW * 2, thick), isBass and c3(30, 60, 150) or c3(185, 40, 40), nil, Enum.Material.SmoothPlastic)
	local nut = spec.nutX * s
	local hw = spec.neckHalfWidth * s
	local neckLen = nut - bodyL * 0.8
	local neck = part(model, "Neck", Vector3.new(neckLen, hw * 2, 0.16 * s), c3(120, 80, 45), nil, Enum.Material.Wood)
	local fret = part(model, "Fretboard", Vector3.new(neckLen, hw * 1.7, 0.03 * s), c3(40, 28, 20), nil, Enum.Material.Wood)
	local head = part(model, "Headstock", Vector3.new(0.45 * s, hw * 2.3, 0.14 * s), c3(60, 40, 25), nil, Enum.Material.Wood)
	local pick = part(model, "Pickup", Vector3.new(0.12 * s, bodyW * 0.9, 0.05 * s), c3(20, 20, 20))
	local bridge = part(model, "Bridge", Vector3.new(0.08 * s, bodyW * 0.8, 0.06 * s), c3(190, 190, 200), nil, Enum.Material.Metal)
	table.insert(prop.parts, { part = body, off = CFrame.new(0, 0, 0) })
	table.insert(prop.parts, { part = neck, off = CFrame.new(bodyL * 0.8 + neckLen / 2, 0, 0.0) })
	table.insert(prop.parts, { part = fret, off = CFrame.new(bodyL * 0.8 + neckLen / 2, 0, 0.095 * s) })
	table.insert(prop.parts, { part = head, off = CFrame.new(nut + 0.22 * s, 0, 0.0) })
	table.insert(prop.parts, { part = pick, off = CFrame.new(spec.strum.X * s - 0.2 * s, 0, thick / 2 + 0.01) })
	table.insert(prop.parts, { part = bridge, off = CFrame.new(spec.strum.X * s + 0.35 * s, 0, thick / 2 + 0.02) })
	-- teller (ince, 4/6)
	local n = isBass and 4 or 6
	for i = 1, n do
		local y = hw * (1 - 2 * (i - 0.5) / n) * 0.85
		local str = part(model, "String" .. i, Vector3.new(nut - (spec.strum.X * s + 0.3 * s), 0.012 * s, 0.012 * s), c3(215, 215, 220), nil, Enum.Material.Metal)
		table.insert(prop.parts, { part = str, off = CFrame.new((nut + spec.strum.X * s + 0.3 * s) / 2, y, 0.135 * s) })
	end
	model.PrimaryPart = body
	function prop.update(self: any, p: any, ctx: any, pose: any)
		local G = layer.G
		for _, it in self.parts do
			it.part.CFrame = G * it.off
		end
	end
	return prop
end

-- ─────────── mikrofon ───────────
local function buildMic(perf: any, parent: any): any
	local layer = perf.instrument
	local model = Instance.new("Model")
	model.Name = "Mic_Prop"
	model.Parent = parent
	local prop = newProp(model)
	local handle = part(model, "Handle", Vector3.new(0.9, 0.16, 0.16), c3(30, 30, 30), Enum.PartType.Cylinder, Enum.Material.Metal)
	local grille = part(model, "Grille", Vector3.new(0.32, 0.32, 0.32), c3(160, 160, 165), Enum.PartType.Ball, Enum.Material.Metal)
	-- mikrofon çerçevesi: -Z (LookVector) = mikrofon başı; silindir ekseni = X -> Z'ye döndür
	local toAxis = CFrame.Angles(0, math.rad(90), 0)
	model.PrimaryPart = handle
	function prop.update(self: any, p: any, ctx: any, pose: any)
		local c = layer.micCF
		handle.CFrame = c * CFrame.new(0, 0, 0.5) * toAxis
		grille.CFrame = c * CFrame.new(0, 0, -0.02)
	end
	return prop
end

-- ─────────── davul seti ───────────
local function buildDrums(perf: any, parent: any): any
	local layer = perf.instrument
	local lay = layer.layout
	local model = Instance.new("Model")
	model.Name = "DrumKit_Prop"
	model.Parent = parent
	local prop = newProp(model)
	local statics = {}
	local floorY = perf.rest.ankle.Right.Y - 0.2 * lay.scale

	for name, p in lay.pieces do
		if p.kind == "kick" then
			local c = cylinderCF(p.pos, Vector3.new(0, 0, 1))
			local shell = part(model, "Kick", Vector3.new(p.thickness, p.radius * 2, p.radius * 2), c3(20, 20, 24), Enum.PartType.Cylinder, Enum.Material.SmoothPlastic)
			shell.CFrame = c
			local head = part(model, "KickHead", Vector3.new(0.04, p.radius * 1.9, p.radius * 1.9), c3(235, 235, 235), Enum.PartType.Cylinder, Enum.Material.SmoothPlastic)
			head.CFrame = cylinderCF(p.pos + Vector3.new(0, 0, p.thickness / 2), Vector3.new(0, 0, 1))
		elseif p.kind == "head" then
			local c = cylinderCF(p.pos - p.normal * (p.thickness / 2 + 0.02), p.normal)
			local shell = part(model, name, Vector3.new(p.thickness, p.radius * 2, p.radius * 2), name == "snare" and c3(200, 200, 205) or c3(180, 30, 30), Enum.PartType.Cylinder, Enum.Material.SmoothPlastic)
			shell.CFrame = c
			local head = part(model, name .. "Head", Vector3.new(0.04, p.radius * 1.9, p.radius * 1.9), c3(240, 240, 240), Enum.PartType.Cylinder, Enum.Material.SmoothPlastic)
			head.CFrame = cylinderCF(p.pos, p.normal)
			-- stand
			local stand = part(model, name .. "Stand", Vector3.new(0.06, math.max(p.pos.Y - floorY - p.thickness, 0.1), 0.06), c3(90, 90, 95), nil, Enum.Material.Metal)
			stand.CFrame = CFrame.new(p.pos.X, floorY + (p.pos.Y - floorY - p.thickness) / 2, p.pos.Z)
		else -- zil
			local c = cylinderCF(p.pos, p.normal)
			local cym = part(model, name, Vector3.new(0.04, p.radius * 2, p.radius * 2), c3(214, 175, 55), Enum.PartType.Cylinder, Enum.Material.Metal)
			cym.CFrame = c
			if name == "hat" then
				prop.hatTop = cym
				prop.hatBase = p
				local bot = part(model, "HatBottom", Vector3.new(0.04, p.radius * 2, p.radius * 2), c3(200, 160, 50), Enum.PartType.Cylinder, Enum.Material.Metal)
				bot.CFrame = cylinderCF(p.pos - p.normal * 0.07, p.normal)
			end
			local stand = part(model, name .. "Stand", Vector3.new(0.05, p.pos.Y - floorY, 0.05), c3(90, 90, 95), nil, Enum.Material.Metal)
			stand.CFrame = CFrame.new(p.pos.X, floorY + (p.pos.Y - floorY) / 2, p.pos.Z)
		end
	end
	-- taburesi
	local stool = part(model, "Stool", Vector3.new(0.35 * lay.scale, 1.0 * lay.scale, 1.0 * lay.scale), c3(25, 25, 28), Enum.PartType.Cylinder, Enum.Material.SmoothPlastic)
	stool.CFrame = CFrame.new(lay.origin.X, lay.origin.Y - 0.35 * lay.scale, lay.origin.Z + 0.05) * CFrame.Angles(0, 0, math.rad(90))
	-- pedallar
	local pedalR = part(model, "KickPedal", Vector3.new(0.5 * lay.scale, 0.06, 1.0 * lay.scale), c3(70, 70, 75), nil, Enum.Material.Metal)
	local pedalL = part(model, "HatPedal", Vector3.new(0.5 * lay.scale, 0.06, 0.9 * lay.scale), c3(70, 70, 75), nil, Enum.Material.Metal)
	local beater = part(model, "Beater", Vector3.new(0.07, 0.07, 0.8 * lay.scale), c3(60, 60, 60), nil, Enum.Material.Metal)
	-- çubuklar
	local sticks = {}
	for _, side in { "Right", "Left" } do
		sticks[side] = part(model, "Stick" .. side, Vector3.new(0.07, 0.07, layer.stickLen), c3(205, 175, 125), nil, Enum.Material.Wood)
	end
	function prop.update(self: any, p: any, ctx: any, pose: any)
		for side, st in sticks do
			local info = layer.sticks[side]
			local back = info.grip - info.dir * layer.gripAt
			local mid = (back + info.tip) / 2
			st.CFrame = CFrame.lookAt(mid, info.tip)
		end
		-- pedal tahtası ayağa uyar: ayak ucu basılınca ön kısım iner
		local pr = lay.pedals.Right
		local pl = lay.pedals.Left
		pedalR.CFrame = CFrame.new(pr.X, pr.Y - 0.12 * lay.scale + layer.pedalLift.Right * 0.5, pr.Z) * CFrame.Angles(layer.footPitch.Right * -0.7, 0, 0)
		pedalL.CFrame = CFrame.new(pl.X, pl.Y - 0.12 * lay.scale + layer.pedalLift.Left * 0.5, pl.Z)
		-- beater: kick pedalı basılınca kick davula yaklaşır
		local kp = lay.pieces.kick.pos
		local press = 1 - math.clamp(layer.pedalLift.Right / (0.18 * lay.scale), 0, 1)
		beater.CFrame = CFrame.new(kp.X, kp.Y - 0.1 * lay.scale, kp.Z + lay.pieces.kick.thickness / 2 + 0.25 * lay.scale - press * 0.2 * lay.scale) * CFrame.Angles(math.rad(10) * (1 - press), 0, 0)
		-- hi-hat: üst zil sol ayakla birlikte kalkar
		if prop.hatTop then
			local hb = prop.hatBase
			prop.hatTop.CFrame = cylinderCF(hb.pos + hb.normal * layer.pedalLift.Left * 0.5, hb.normal)
		end
	end
	return prop
end

--[[ kind: "Guitar" | "Bass" | "Drums" | "Vocal". Dönüş: Prop (update(perf, ctx, pose) her karede çağrılır) ]]
function PropBuilder.build(kind: string, perf: any, parent: any): any
	if kind == "Guitar" or kind == "Bass" then
		return buildStringed(kind, perf, parent)
	elseif kind == "Drums" then
		return buildDrums(perf, parent)
	elseif kind == "Vocal" then
		return buildMic(perf, parent)
	end
	error("PropBuilder: bilinmeyen rol " .. tostring(kind))
end

--[[ Kullanıcının kendi modelini kullan: <Rol>_Prop (PrimaryPart = enstrüman çerçevesi). Stringed ve mikrofon için çalışır. ]]
function PropBuilder.adopt(model: any, kind: string, perf: any): any
	local prop = newProp(model)
	local layer = perf.instrument
	function prop.update(self: any, p: any, ctx: any, pose: any)
		if kind == "Vocal" then
			model:PivotTo(layer.micCF)
		else
			model:PivotTo(layer.G)
		end
	end
	return prop
end

return PropBuilder
]===])
local F_Data = mk(root, "Folder", "Data")
mk(F_Data, "ModuleScript", "SongMap", [===[
--!strict
--[[ OTOMATİK ÜRETİLDİ: roblox/tools/analyze_song.py - elle düzenleme, aracı yeniden çalıştır.
     kaynak: /root/.claude/uploads/2c67526d-162e-50b7-a3d8-f6dcef408f38/4e357496-fever_dream.mp3  süre: 172.17s ]]
return {
	bpm = 160.000,
	beatsPerBar = 4,
	slotsPerBar = 16,
	firstBarTime = 0.3906, -- ilk ölçü başı (sn)
	dropTime = 6.403,
	duration = 172.173,
	bars = 114,
	sectionStarts = {0, 4, 12, 16, 24, 28, 44, 52, 108}, -- ölçü indeksi (0 tabanlı)
	energy = {0.57, 0.54, 0.75, 0.68, 0.94, 0.96, 0.96, 0.81, 0.96, 0.94, 0.98, 0.87, 0.65, 0.60, 0.80, 0.82, 0.83, 0.81, 0.82, 0.82, 0.85, 0.86, 0.83, 0.84, 0.83, 0.80, 0.60, 0.62, 0.96, 0.92, 0.97, 0.97, 0.92, 0.93, 0.91, 0.92, 0.91, 0.90, 0.92, 0.91, 0.90, 0.93, 0.90, 0.91, 0.85, 0.76, 0.80, 0.72, 0.79, 0.75, 0.78, 0.60, 0.92, 0.85, 0.95, 0.90, 0.88, 0.87, 0.96, 0.74, 0.97, 0.90, 0.95, 0.96, 0.93, 0.94, 0.93, 0.97, 0.91, 0.91, 0.92, 0.92, 0.92, 0.93, 0.91, 0.96, 0.57, 1.00, 0.94, 0.94, 0.81, 0.99, 1.00, 0.97, 0.73, 0.91, 0.92, 0.94, 0.91, 0.88, 0.86, 0.89, 0.60, 0.99, 0.95, 0.93, 0.96, 0.99, 0.96, 0.98, 0.57, 0.91, 0.92, 0.91, 0.76, 0.94, 0.94, 0.90, 0.98, 0.73, 0.55, 0.60, 0.51, 0.00}, -- ölçü başına 0..1
	bass = {27, 27, 27, 27, 25, 25, 25, 25, 28, 31, 31, 31, 34, 34, 34, 0, 27, 27, 27, 0, 0, 25, 25, 0, 31, 31, 31, 31, 37, 34, 34, 35, 0, 27, 27, 0, 0, 25, 25, 0, 31, 31, 31, 31, 34, 34, 34, 35, 27, 27, 27, 27, 25, 27, 25, 25, 0, 31, 31, 0, 0, 35, 35, 34, 0, 27, 27, 0, 0, 27, 25, 0, 33, 31, 31, 0, 35, 34, 34, 34, 0, 27, 27, 0, 0, 25, 25, 0, 0, 31, 31, 0, 0, 34, 34, 34, 0, 27, 27, 0, 0, 25, 25, 25, 32, 32, 32, 31, 34, 34, 34, 34, 0, 27, 27, 0, 0, 25, 25, 0, 31, 31, 31, 31, 0, 34, 34, 35, 0, 27, 27, 0, 25, 25, 25, 0, 31, 31, 31, 31, 0, 0, 0, 0, 0, 27, 0, 27, 25, 25, 0, 0, 31, 31, 31, 31, 34, 34, 0, 0, 27, 27, 0, 27, 25, 25, 25, 0, 31, 31, 31, 31, 34, 36, 34, 35, 0, 0, 0, 0, 25, 25, 25, 26, 30, 31, 31, 31, 33, 34, 34, 0, 26, 27, 27, 27, 27, 25, 25, 25, 0, 31, 31, 31, 34, 34, 33, 0, 0, 0, 35, 32, 0, 0, 0, 41, 34, 33, 32, 0, 0, 0, 0, 0, 0, 0, 35, 33, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 27, 27, 0, 0, 25, 25, 0, 31, 31, 31, 0, 0, 34, 34, 35, 34, 27, 27, 0, 25, 25, 25, 0, 32, 31, 31, 33, 35, 34, 34, 0, 0, 27, 27, 27, 25, 25, 25, 25, 31, 31, 31, 31, 34, 34, 34, 0, 0, 27, 27, 27, 25, 25, 25, 0, 31, 31, 0, 0, 0, 0, 0, 0, 33, 32, 32, 32, 28, 27, 29, 27, 27, 26, 27, 27, 27, 27, 0, 27, 26, 27, 27, 0, 27, 27, 0, 27, 27, 28, 27, 27, 27, 27, 27, 27, 27, 0, 0, 0, 0, 27, 31, 27, 27, 0, 0, 0, 0, 27, 27, 0, 27, 0, 0, 0, 0, 27, 0, 0, 27, 27, 0, 0, 0, 27, 0, 0, 0, 0, 26, 26, 0, 0, 27, 27, 0, 0, 0, 0, 0, 0, 31, 31, 34, 35, 35, 34, 27, 0, 27, 27, 0, 0, 0, 0, 31, 32, 31, 0, 0, 0, 0, 0, 0, 0, 27, 27, 25, 25, 25, 0, 31, 31, 31, 31, 34, 34, 34, 0, 27, 27, 27, 27, 25, 25, 25, 0, 31, 31, 31, 31, 34, 34, 34, 39, 36, 33, 32, 28, 25, 25, 25, 25, 31, 31, 31, 31, 34, 34, 34, 43, 26, 26, 25, 25}, -- vuruş başına MIDI (0=yok)
	chords = {
		{3, "M", 0.90}, -- D#M
		{3, "M", 0.91}, -- D#M
		{0, "m", 0.81}, -- Cm
		{0, "m", 0.73}, -- Cm
		{7, "m", 0.71}, -- Gm
		{7, "M", 0.75}, -- GM
		{10, "M", 0.81}, -- A#M
		{10, "M", 0.60}, -- A#M
		{3, "M", 0.69}, -- D#M
		{3, "M", 0.60}, -- D#M
		{0, "m", 0.69}, -- Cm
		{0, "M", 0.67}, -- CM
		{7, "m", 0.69}, -- Gm
		{7, "m", 0.62}, -- Gm
		{10, "M", 0.72}, -- A#M
		{10, "M", 0.62}, -- A#M
		{3, "M", 0.67}, -- D#M
		{3, "M", 0.65}, -- D#M
		{0, "m", 0.73}, -- Cm
		{0, "m", 0.68}, -- Cm
		{7, "m", 0.70}, -- Gm
		{7, "m", 0.66}, -- Gm
		{10, "M", 0.68}, -- A#M
		{10, "M", 0.72}, -- A#M
		{3, "M", 0.81}, -- D#M
		{3, "M", 0.82}, -- D#M
		{0, "m", 0.82}, -- Cm
		{0, "m", 0.76}, -- Cm
		{7, "m", 0.70}, -- Gm
		{7, "m", 0.65}, -- Gm
		{7, "m", 0.66}, -- Gm
		{3, "M", 0.67}, -- D#M
		{3, "M", 0.65}, -- D#M
		{3, "M", 0.68}, -- D#M
		{0, "m", 0.69}, -- Cm
		{0, "m", 0.66}, -- Cm
		{7, "m", 0.73}, -- Gm
		{2, "m", 0.57}, -- Dm
		{7, "m", 0.67}, -- Gm
		{3, "M", 0.72}, -- D#M
		{3, "M", 0.72}, -- D#M
		{10, "m", 0.67}, -- A#m
		{5, "m", 0.65}, -- Fm
		{0, "m", 0.63}, -- Cm
		{7, "m", 0.70}, -- Gm
		{10, "M", 0.71}, -- A#M
		{10, "M", 0.63}, -- A#M
		{10, "m", 0.68}, -- A#m
		{3, "M", 0.72}, -- D#M
		{3, "M", 0.70}, -- D#M
		{0, "m", 0.68}, -- Cm
		{3, "M", 0.63}, -- D#M
		{1, "M", 0.57}, -- C#M
		{7, "m", 0.68}, -- Gm
		{10, "M", 0.84}, -- A#M
		{10, "M", 0.78}, -- A#M
		{3, "M", 0.72}, -- D#M
		{3, "M", 0.62}, -- D#M
		{0, "m", 0.69}, -- Cm
		{0, "M", 0.66}, -- CM
		{7, "m", 0.70}, -- Gm
		{7, "m", 0.63}, -- Gm
		{10, "M", 0.68}, -- A#M
		{7, "m", 0.60}, -- Gm
		{3, "M", 0.67}, -- D#M
		{3, "M", 0.66}, -- D#M
		{0, "m", 0.74}, -- Cm
		{0, "m", 0.68}, -- Cm
		{7, "m", 0.72}, -- Gm
		{7, "m", 0.62}, -- Gm
		{10, "M", 0.69}, -- A#M
		{10, "M", 0.67}, -- A#M
		{3, "M", 0.67}, -- D#M
		{3, "M", 0.62}, -- D#M
		{0, "m", 0.77}, -- Cm
		{0, "m", 0.73}, -- Cm
		{7, "m", 0.73}, -- Gm
		{7, "m", 0.72}, -- Gm
		{10, "M", 0.66}, -- A#M
		{7, "m", 0.61}, -- Gm
		{3, "M", 0.65}, -- D#M
		{10, "M", 0.65}, -- A#M
		{0, "m", 0.70}, -- Cm
		{0, "m", 0.68}, -- Cm
		{0, "m", 0.64}, -- Cm
		{7, "m", 0.74}, -- Gm
		{10, "M", 0.67}, -- A#M
		{10, "M", 0.63}, -- A#M
		{8, "M", 0.68}, -- G#M
		{3, "M", 0.63}, -- D#M
		{0, "m", 0.67}, -- Cm
		{0, "m", 0.67}, -- Cm
		{7, "m", 0.76}, -- Gm
		{7, "m", 0.75}, -- Gm
		{7, "m", 0.71}, -- Gm
		{10, "M", 0.69}, -- A#M
		{3, "M", 0.59}, -- D#M
		{3, "M", 0.70}, -- D#M
		{0, "m", 0.83}, -- Cm
		{0, "m", 0.67}, -- Cm
		{7, "m", 0.67}, -- Gm
		{7, "m", 0.75}, -- Gm
		{3, "M", 0.75}, -- D#M
		{5, "M", 0.57}, -- FM
		{0, "M", 0.55}, -- CM
		{5, "m", 0.65}, -- Fm
		{0, "M", 0.72}, -- CM
		{0, "m", 0.57}, -- Cm
		{7, "M", 0.61}, -- GM
		{7, "M", 0.60}, -- GM
		{5, "m", 0.59}, -- Fm
		{10, "M", 0.69}, -- A#M
		{0, "m", 0.65}, -- Cm
		{5, "m", 0.61}, -- Fm
		{0, "M", 0.71}, -- CM
		{5, "m", 0.56}, -- Fm
		{7, "m", 0.60}, -- Gm
		{0, "M", 0.62}, -- CM
		{0, "m", 0.59}, -- Cm
		{7, "m", 0.56}, -- Gm
		{3, "M", 0.69}, -- D#M
		{3, "M", 0.62}, -- D#M
		{0, "m", 0.69}, -- Cm
		{0, "M", 0.65}, -- CM
		{7, "m", 0.73}, -- Gm
		{7, "m", 0.60}, -- Gm
		{10, "M", 0.65}, -- A#M
		{7, "m", 0.60}, -- Gm
		{3, "M", 0.68}, -- D#M
		{3, "M", 0.68}, -- D#M
		{0, "m", 0.73}, -- Cm
		{0, "m", 0.65}, -- Cm
		{7, "m", 0.70}, -- Gm
		{7, "m", 0.66}, -- Gm
		{10, "M", 0.65}, -- A#M
		{10, "M", 0.64}, -- A#M
		{3, "M", 0.64}, -- D#M
		{3, "M", 0.62}, -- D#M
		{0, "m", 0.76}, -- Cm
		{0, "m", 0.70}, -- Cm
		{7, "m", 0.72}, -- Gm
		{7, "M", 0.72}, -- GM
		{10, "M", 0.65}, -- A#M
		{7, "m", 0.58}, -- Gm
		{3, "M", 0.66}, -- D#M
		{10, "M", 0.62}, -- A#M
		{0, "m", 0.72}, -- Cm
		{0, "m", 0.68}, -- Cm
		{7, "m", 0.63}, -- Gm
		{7, "m", 0.65}, -- Gm
		{10, "M", 0.69}, -- A#M
		{10, "M", 0.67}, -- A#M
		{8, "M", 0.74}, -- G#M
		{8, "M", 0.63}, -- G#M
		{3, "M", 0.68}, -- D#M
		{8, "M", 0.64}, -- G#M
		{3, "m", 0.65}, -- D#m
		{3, "M", 0.69}, -- D#M
		{0, "m", 0.66}, -- Cm
		{8, "M", 0.62}, -- G#M
		{0, "m", 0.64}, -- Cm
		{10, "M", 0.55}, -- A#M
		{8, "M", 0.66}, -- G#M
		{8, "M", 0.64}, -- G#M
		{0, "m", 0.56}, -- Cm
		{3, "M", 0.67}, -- D#M
		{3, "M", 0.71}, -- D#M
		{8, "M", 0.57}, -- G#M
		{3, "m", 0.55}, -- D#m
		{10, "m", 0.57}, -- A#m
		{3, "M", 0.65}, -- D#M
		{0, "m", 0.59}, -- Cm
		{3, "M", 0.68}, -- D#M
		{3, "M", 0.70}, -- D#M
		{3, "M", 0.73}, -- D#M
		{0, "m", 0.61}, -- Cm
		{0, "m", 0.63}, -- Cm
		{0, "m", 0.60}, -- Cm
		{8, "M", 0.65}, -- G#M
		{3, "M", 0.64}, -- D#M
		{3, "M", 0.64}, -- D#M
		{3, "M", 0.67}, -- D#M
		{3, "M", 0.69}, -- D#M
		{5, "m", 0.61}, -- Fm
		{10, "m", 0.69}, -- A#m
		{2, "M", 0.59}, -- DM
		{3, "m", 0.65}, -- D#m
		{3, "M", 0.64}, -- D#M
		{0, "m", 0.72}, -- Cm
		{0, "m", 0.64}, -- Cm
		{7, "m", 0.69}, -- Gm
		{7, "m", 0.68}, -- Gm
		{7, "m", 0.60}, -- Gm
		{10, "M", 0.63}, -- A#M
		{3, "M", 0.65}, -- D#M
		{3, "M", 0.63}, -- D#M
		{0, "m", 0.69}, -- Cm
		{0, "m", 0.64}, -- Cm
		{7, "m", 0.70}, -- Gm
		{0, "m", 0.66}, -- Cm
		{2, "m", 0.66}, -- Dm
		{2, "m", 0.63}, -- Dm
		{3, "M", 0.71}, -- D#M
		{3, "M", 0.63}, -- D#M
		{0, "m", 0.71}, -- Cm
		{0, "m", 0.64}, -- Cm
		{7, "m", 0.72}, -- Gm
		{7, "m", 0.71}, -- Gm
		{10, "M", 0.73}, -- A#M
		{10, "M", 0.59}, -- A#M
		{3, "M", 0.70}, -- D#M
		{3, "M", 0.66}, -- D#M
		{0, "m", 0.75}, -- Cm
		{0, "m", 0.70}, -- Cm
		{7, "m", 0.65}, -- Gm
		{7, "m", 0.71}, -- Gm
		{10, "M", 0.66}, -- A#M
		{10, "M", 0.63}, -- A#M
		{3, "M", 0.81}, -- D#M
		{3, "M", 0.81}, -- D#M
		{0, "m", 0.86}, -- Cm
		{0, "M", 0.81}, -- CM
		{7, "m", 0.90}, -- Gm
		{7, "M", 0.88}, -- GM
		{10, "M", 0.92}, -- A#M
		{7, "m", 0.77}, -- Gm
		{2, "m", 0.61}, -- Dm
		{2, "m", 0.54}, -- Dm
	}, -- yarım ölçü başına {kök pc, kalite, güven}
	lanes = { -- ölçü başına 16 hane: 0-9 şiddet, '.' yok
		{k="9...22........2.", s="91.15.1.2....24.", h="................", c="................", g="937.917264932294"},
		{k=".2....3.2241.112", s=".12.111.1.....3.", h="1.....2.1.3...2.", c="................", g="7686979271914396"},
		{k="7.6.1.1..17...3.", s="5.6.8.25..7.7.6.", h="9.5.9.889.459.9.", c="................", g="93938198.29.9291"},
		{k="8...3....19....7", s="7.115..6.87.7.25", h="9.9.9.98942.5...", c="...............9", g="91726185.34.2.29"},
		{k="9.3.41..141.315.", s="9.6241.2.21131..", h="9...1...1.334.1.", c="................", g="911.2....22...11"},
		{k="4.7.13311.5..5..", s="..212......132..", h="3.2.6...2.2.3...", c="................", g=".11....1..3.1..."},
		{k="1.2.2.1.4.7.164.", s="...12..12...4..2", h="3.1.4.1.2.334.1.", c="................", g="..11..21.1.1...."},
		{k="1.3..14.9.523.25", s="..3.4....75.8399", h="3.2.5...2.3.3999", c="................", g="2.2..111.....999"},
		{k="9.21..1...4..34.", s="9.4.5.11....4...", h="9...3...2.124...", c="................", g="9.21..1...2.1..."},
		{k="1.6..32.1.3.22.1", s=".2..11..211162..", h="312.5...1.2.4.1.", c="................", g=".11.....1.2....."},
		{k="1.6.411.1.6..25.", s="1...1.112...41.1", h="4.1.5...2.234.1.", c="................", g="21213....1.....1"},
		{k="3.6.243.214.2.1.", s=".12.321..25..26.", h="4.2.5...2.3..23.", c="................", g="1.21..11....2..."},
		{k="33.1.1..21......", s="..1.8....12.1...", h="....1.2.4.55..6.", c="................", g="...2.25.....4172"},
		{k="2.321.2..4...332", s="9.2.3.3.1.2.7...", h="..7.1.7.6.5...93", c="................", g="429.3.1.21813.82"},
		{k="4.7...2...7...6.", s=".12.7.1.1.4.8.1.", h="..3.1...8.5.8.2.", c="................", g="8.61931...4.936."},
		{k="3.81.39..17..111", s="2.2.7.111...92..", h="9.1.9.2.611.9..1", c="................", g="9.9.92.1..521..."},
		{k="7.9.21..136.128.", s="2.36......5.7.2.", h="8.4.4...5..23.1.", c="................", g="219.5..1..214.41"},
		{k="8.7.331..15.29.1", s="..2.7.....2.9.3.", h="1.6.1...6.612.11", c="................", g="324261.1..32913."},
		{k="6.5.323.3.7.216.", s="..5.8....16.2.3.", h="9.7.9...7.4.9.2.", c="................", g="9.9191..6.615.4."},
		{k="5.6.1131..9....2", s="2.2.4.23..2.5.1.", h="311.9..32.4.9...", c="................", g="429.71........4."},
		{k="8.6.1.11..6..17.", s="4.3.5..1139.613.", h="812.....6.6.6.21", c="................", g=".32.113....13.11"},
		{k="5.7.4..2226..9.1", s="315.6.2.3.1.92..", h="..6.9...7.4.8..1", c="................", g="121...22..71...."},
		{k="5.8.23...16...9.", s="2.4.9.5...1.7.1.", h="91653.211.6.9.23", c="................", g="..4.612.1....1.."},
		{k="4.6..2.6.26.....", s="2...3.25..31912.", h="..6.6.141.4.9.11", c="................", g="712.5.41..11.1.3"},
		{k="7.8.1..2115.2.6.", s=".4..9...1.3.9.1.", h="8.232.3.2.5.2.2.", c="................", g="....513.116.1111"},
		{k="8.6.21.23.4.2232", s="3.2.9...4.199325", h="1.662...7.2562.3", c="................", g="121.5.51..2...21"},
		{k="1...1.....1.1...", s="..4.2.3321...14.", h="..6.2.5.7.715...", c="................", g="......2....1..1."},
		{k="2.311.1215...22.", s=".11.5.123.....4.", h="5.6.7.223.3.3.22", c="................", g="......1..21.1..."},
		{k="9.2.444..23...1.", s="5...5....5..3.21", h="6...2.1.2.221.1.", c="................", g="..2...4...2.11.."},
		{k="4.4..2431.6..6..", s="....3...2.1.612.", h="2.2.3...2..1.11.", c="................", g=".2.11....11111.."},
		{k="4.7.1212.19.142.", s=".11.3...223.6.1.", h="2.1.2...2.112.1.", c="................", g="2..1.......1...."},
		{k="4.5.2.339464..1.", s=".1..1121.15.12.4", h="2.1.3...1..23111", c="................", g="1.3....1.121..51"},
		{k="5.4.1..3..3...4.", s="1.237..1.4..6.2.", h="..1.1.1.2.233...", c="................", g="11.11.2........."},
		{k="5.7..1..314.13..", s="2...3...2222431.", h="4.1.4...1.1.3.13", c="................", g="111.......1..1.1"},
		{k="2.623.133.4..21.", s="1.2.........41.3", h="..1.1...1.133.1.", c="................", g="1..11..........."},
		{k="3.7.422.3161.62.", s=".4.24.3.1.115.23", h="4.2.6...2.1212.1", c="................", g="111........11.12"},
		{k="1.1....15.111.22", s="..1.5.1.1...6...", h="1...1.1.2.131...", c="................", g="..11.11........."},
		{k="8.7.2.214.212232", s="...42..11...221.", h="3.1.41....1.5...", c="................", g=".........1....2."},
		{k="4.2.4...8.2...2.", s="1...5..12.315...", h="3.1.6.1.2.125..1", c="................", g=".1...........1.."},
		{k="4...8.213.62.256", s="..6.3.1..1.1.345", h=".22.3...3.1.4111", c="................", g="4..1...1.....1.."},
		{k="9..21..32...2.1.", s="11214.121.2.6.11", h="....1...2..32.1.", c="................", g="4...11.......1.."},
		{k="6.12..2.5.423.4.", s="2.5...12.1.1.4..", h="3.1.3...2.1.3...", c="................", g="....1.1..1...1.."},
		{k="521.2..13.3.7...", s="....4.3.4.1.4.2.", h="3.1.5.1...135...", c="................", g=".11...11........"},
		{k="5..1157.3.21531.", s="..3.51221.8.214.", h="2.1.1.11..4.1.12", c="................", g="..2.11..2......."},
		{k="5.222..1.13.4411", s="6.281..25.3.6.6.", h="1.2.3.4282.282..", c="................", g="...1212...6....1"},
		{k="4.42.811..4.4.8.", s="914.7.39467.6.9.", h="229.9.9423..9.6.", c="................", g=".53.918.6.62..21"},
		{k="5.9...2.2.8.4.21", s="5.9.1..552731.2.", h="1.3.8.521.948.6.", c="................", g=".13.1.443.3.3..."},
		{k="6.9.7.4.916.2.7.", s="5.9.7.2.423.9.9.", h="5.9.8.851234112.", c="................", g="229.114.22117.2."},
		{k="8.9.2...3.4.3.5.", s="5.9.31981.424.1.", h="5.612.119.3.8.6.", c="................", g="5.8.121.11111.21"},
		{k="5.8...164.4.4.8.", s="6.83...7646...71", h="6.4.7.45722.4.3.", c="................", g=".1.14.....1.122."},
		{k="6.9.5.4.724.2.2.", s="946.3.242.713.5.", h="11.251153.251.9.", c="................", g="53513.4.2...2..1"},
		{k="5.9.4.3.2..1....", s="5.9.5..815149...", h="4...7.211212..9.", c="................", g="..3.1.2.1.9.9254"},
		{k="91...532..43.234", s="9.32.11311..1.92", h="4..1212.1...5.9.", c="................", g="1244223..1116.5."},
		{k="9.42511.113...92", s="31..42..22..1.73", h="..1.911.4...5244", c="................", g="..116.3.....4.1."},
		{k="41.25312.1318..2", s="8...1...54......", h="321242346...5.12", c="................", g="..12211322325.22"},
		{k="..3.91.1.32.5231", s="141.322.22..1111", h="4...71225.161.52", c="................", g=".3..61233.221123"},
		{k="2124.31.1.2...44", s="21..2...41...195", h="1...2...1...5.11", c="................", g="2.311.2.31.11..."},
		{k="9..17.1.4111.146", s=".2..511.941.4136", h="...2....4.1.4334", c="................", g="....3.11.2226..1"},
		{k="8.11543412139.23", s="2.21....561.2..1", h="2..111125...3222", c="................", g="2..1.12...1.1121"},
		{k="....9111..2..5..", s="...5.1...2...12.", h="2...41.34..2....", c="................", g="1.1.31.32...2..."},
		{k="9.3.3.3..23...2.", s="3.4.5.23111.2.22", h="4...2...2.231.1.", c="................", g="3.4...1...1..13."},
		{k="2.6..331..7.15..", s="..2.2......4424.", h="3.2.3...2.11.1..", c="................", g=".1...11.1...1.11"},
		{k="3.4.2..23.7..44.", s=".11.5....21.5.2.", h="3.1.2...1..32.1.", c="................", g="3.1.......21...."},
		{k="..3..2219375.141", s="..2.321..13.2414", h="1.1.21..2.122.11", c="................", g="1...1....11...3."},
		{k="312.1.....3...1.", s="132.31.2..1.6211", h="1.1.1.1.2.232...", c="................", g=".13............."},
		{k="4.7...1.134.23.1", s="1..14...2..1322.", h="3.1.4.1.2..14112", c="................", g=".1211.....2.1.21"},
		{k="3.6..22.1.4.1321", s="2.1.3..14.1.4.11", h="..1.1...1.232.1.", c="................", g="11..21........1."},
		{k="2.514.4..251.32.", s="....611193..822.", h="3.1.411.6.112111", c="................", g="21.......2.1...."},
		{k="4...1.1.4.11...2", s=".34.4..21...4...", h="3...1.1.2.131...", c="................", g="1...11..1.1.1..."},
		{k="5.....1.5.41....", s="1.232..21..3122.", h="2.1.5...1.2.4...", c="................", g=".....1..3...1.1."},
		{k="3.112.639...3.1.", s="1.1.4...4...6.1.", h="3.1.511.4.144..1", c="................", g="........1......."},
		{k="4..18.117.6.1.26", s="....3.31..2..213", h=".22.21..3.2.4111", c="................", g="4.21.1.2..1.211."},
		{k="7..1....6.1...1.", s=".3.12132.21.4.12", h="....1...3.123...", c="................", g="4..1.......1...."},
		{k="3.2.1.5.8.222.2.", s="..6....3...11.2.", h="3.1.2...2.2.2.1.", c="................", g="....3.2..1..1..."},
		{k="21311.224.2.5.1.", s=".1..5..25.2.8.11", h="4.1.31....245...", c="................", g="111....1...1...."},
		{k="4.6..35.4.1.5141", s="1.1.33..1.6.2.33", h="2...2.11..4.2.34", c="................", g="..3..1..1....1.2"},
		{k=".3153..12..1..52", s="..25.........182", h="1.2...1...1..36.", c="................", g="........11...54."},
		{k="6.3...6.41339...", s="5.3...6.32..21..", h="2...1.2.7..27.1.", c="................", g="7211..4.1.137241"},
		{k=".13.....9.3.3.2.", s="112.....9.11..12", h="4...71.36.1.2.51", c="................", g=".1..12224..11.3."},
		{k="5.31..9.213.9...", s="3...1.5.332.6.1.", h="....1.215...512.", c="................", g="42...141511.766."},
		{k="1...9.12328....1", s=".12.8...93.3.421", h="8...9...9..12442", c="................", g="1...311.1.464312"},
		{k="4.....4..1..8...", s="9..2..1561..9.4.", h="....2.231.1..335", c="................", g="1.1...222.21912."},
		{k=".2..4.149.6..24.", s="2...3..12.123.91", h="..21....9.1...61", c="................", g="3...2.2.3......."},
		{k="2...2.714.3.9.12", s=".12...3.32.1.1..", h="....2...5...1...", c="................", g="411.211.11.1413."},
		{k="4..29.121.3.4.34", s="...4..1.5.16.11.", h="1...1...........", c="................", g="....11...1....1."},
		{k="4.2.323...9.6.5.", s="2.1.33..3.6493.1", h="4.1.1..1..12..3.", c="................", g="81311..141.12.1."},
		{k="119.3..38.5.23.3", s="....5.255...2..1", h="1...2..1..1...23", c="................", g="..1........111.3"},
		{k="..3.1.12..93241.", s=".11.3.1.....81..", h="2..12..1...14...", c="................", g="4.311.1.1.1...2."},
		{k="212.....962..1.2", s=".1..6.2.114.2..2", h="1.114...312131.3", c="................", g="...11.1.21222..."},
		{k="4.7..1116.5.3.4.", s=".13.24211.5.42.5", h="....1.1...12...1", c="................", g=".........1.321.1"},
		{k="223.2..77.5..4.2", s="...232.23..321.1", h="..1.4..3....2.12", c="................", g="..21..226......4"},
		{k="6.1.126.2.9.6.2.", s="1.1..2...2.39.2.", h="..113..23...1.1.", c="................", g="2...111...584111"},
		{k="1.2.4.1.21.12...", s="..24223.12.1.3.1", h="3.22...1.3......", c="................", g="2.1.1.3.....2.1."},
		{k="7...4.3.322.3..1", s="7.1.21..5.....21", h="6...11214.12..1.", c="................", g="5.11..11..2..11."},
		{k="7.3.3.5..25.3.11", s="..1.1.1.8..2214.", h="3...222.3..1.31.", c="................", g="31....1...112.1."},
		{k="4..14.6...4.4.1.", s=".22...2.31....1.", h="3.1.121.4..22.1.", c="................", g="4.221.....211..."},
		{k="8..16.5.243.4...", s="1.2.12..1......1", h="2.3.121.4...211.", c="................", g=".121...111....4."},
		{k="5...7.3.....5...", s="21..31..92..241.", h="3.1.1.3.5.13311.", c="................", g="1.111111..2.1..."},
		{k="4...5.6..15.2.51", s="....1...5.....1.", h="3.1.321.4...2223", c="................", g="12212.2...1.3.1."},
		{k="6.1.5.3.425..1..", s="5.....2.211.4.3.", h="..1.111.4.123.3.", c="................", g="11..........1..2"},
		{k="4.....1.1..95124", s="..1.1.1.1..972..", h="........1.1.11..", c="................", g="........9.9.3.4."},
		{k="7...61..5.3.3.3.", s="1...2.....1.3.2.", h="....1.1.3..21...", c="................", g="1.......11...1.."},
		{k="3..13.342...3.1.", s="...12.1.1.112...", h="3.1.4.1...1.5...", c="................", g="..........113.1."},
		{k="2...413.7...2..2", s="....41...1..4...", h="3.1.411.3.133..1", c="................", g="1.....1.11......"},
		{k="6.3.5.1...14..25", s="....3..1...9...9", h=".12.51..1.132331", c="................", g="3..1.111..163.1."},
		{k="9.1..14.8...2.2.", s="1.1.4122..2.6...", h="5...1.1.3.132.1.", c="................", g="5...1.......11.."},
		{k="4.2.1...3..31.52", s="..2.11.11..113..", h="3.1.3.1.2.1.3.1.", c="................", g="...121...2..11.1"},
		{k="5.4.3..16.3.5.1.", s="2.1.5...2...3.2.", h="3.1.4.1...234...", c="................", g="1.3.11.....1...2"},
		{k="41.34.413...15..", s="12..7.....4..141", h="2.1.1.22..3.1.14", c="................", g="....1..11...1..."},
		{k="5.1...21.1231.11", s="..5.1...32361.3.", h="2.2.............", c="................", g=".....11...1....1"},
		{k=".3..11.2.51.221.", s="....3......24.41", h="................", c="................", g="1...1.1..1..1..2"},
		{k="1...2........11.", s="2.115....1.1.16.", h="................", c="................", g="21...13.......12"},
		{k="..51.2..32.25.3.", s=".....27.23.13.24", h="................", c="................", g="....1.8......144"},
		{k="1...............", s="1..4............", h="................", c="................", g="21.............."},
	},
}
]===])
local F_Rig = mk(root, "Folder", "Rig")
mk(F_Rig, "ModuleScript", "R15Rig", [===[
--!strict
--[[
	R15 rig bağlama + kendi ileri kinematiği (FK).

	Var olan Motor6D'leri DEĞİŞTİRMEZ: yalnızca Transform'u yazar (C0/C1 olduğu gibi kalır).
	Bunun anlamı: modele dokunmadan animasyon verirsin; sistemi kapatınca rig eski haline döner.
	FK'yi Roblox'a bırakmayıp kendimiz hesaplıyoruz çünkü IK ve enstrüman hedefleri aynı karede
	kemiklerin dünya konumuna ihtiyaç duyuyor (Roblox'un fizik/animasyon güncellemesini beklemeden).

	Eklem sırası (üst -> alt): Root, Waist, Neck, {R,L}Shoulder/Elbow/Wrist, {R,L}Hip/Knee/Ankle.
]]

local Root = script:FindFirstAncestor("BandPerformance")
local IK = require(Root.Rig.TwoBoneIK)

export type Joint = {
	name: string,
	motor: any, -- Motor6D
	part0: string,
	part1: string,
	c0: CFrame,
	c1: CFrame,
	bone: Vector3, -- eklem uzayında, çocuk eklemine vektör (yoksa sıfır)
}

export type Rig = {
	model: Model,
	joints: { [string]: Joint },
	order: { string },
	rootCF: CFrame,
	lengths: { armUpper: number, armLower: number, legUpper: number, legLower: number, reach: number },
	partCF: { [string]: CFrame },
}

local R15Rig = {}
R15Rig.__index = R15Rig

-- {eklem, Part0, Part1, çocuk eklem (kemik yönü için)}
local DEF: { { string } } = {
	{ "Root", "HumanoidRootPart", "LowerTorso", "Waist" },
	{ "Waist", "LowerTorso", "UpperTorso", "Neck" },
	{ "Neck", "UpperTorso", "Head", "" },
	{ "RightShoulder", "UpperTorso", "RightUpperArm", "RightElbow" },
	{ "RightElbow", "RightUpperArm", "RightLowerArm", "RightWrist" },
	{ "RightWrist", "RightLowerArm", "RightHand", "" },
	{ "LeftShoulder", "UpperTorso", "LeftUpperArm", "LeftElbow" },
	{ "LeftElbow", "LeftUpperArm", "LeftLowerArm", "LeftWrist" },
	{ "LeftWrist", "LeftLowerArm", "LeftHand", "" },
	{ "RightHip", "LowerTorso", "RightUpperLeg", "RightKnee" },
	{ "RightKnee", "RightUpperLeg", "RightLowerLeg", "RightAnkle" },
	{ "RightAnkle", "RightLowerLeg", "RightFoot", "" },
	{ "LeftHip", "LowerTorso", "LeftUpperLeg", "LeftKnee" },
	{ "LeftKnee", "LeftUpperLeg", "LeftLowerLeg", "LeftAnkle" },
	{ "LeftAnkle", "LeftLowerLeg", "LeftFoot", "" },
}

R15Rig.JOINT_ORDER = {}
for _, d in DEF do
	table.insert(R15Rig.JOINT_ORDER, d[1])
end

local function findMotor(model: Model, name: string): any
	local m = model:FindFirstChild(name, true)
	if m == nil then
		error(("R15Rig: '%s' Motor6D'si bulunamadı (%s). R15 rig gerekli."):format(name, model.Name))
	end
	return m
end

function R15Rig.new(model: Model): Rig
	local joints: { [string]: Joint } = {}
	local order = {}
	local motors: { [string]: any } = {}
	for _, d in DEF do
		motors[d[1]] = findMotor(model, d[1])
	end
	for _, d in DEF do
		local m = motors[d[1]]
		local childName = d[4]
		local bone = Vector3.new(0, 0, 0)
		if childName ~= "" then
			bone = m.C1:Inverse() * motors[childName].C0.Position
		end
		joints[d[1]] = {
			name = d[1], motor = m, part0 = d[2], part1 = d[3],
			c0 = m.C0, c1 = m.C1, bone = bone,
		}
		table.insert(order, d[1])
	end
	local hrp = model:FindFirstChild("HumanoidRootPart", true)
	local self = setmetatable({
		model = model,
		joints = joints,
		order = order,
		rootCF = hrp and hrp.CFrame or CFrame.identity,
		partCF = {},
		lengths = {
			armUpper = joints.RightShoulder.bone.Magnitude,
			armLower = joints.RightElbow.bone.Magnitude,
			legUpper = joints.RightHip.bone.Magnitude,
			legLower = joints.RightKnee.bone.Magnitude,
			reach = joints.RightShoulder.bone.Magnitude + joints.RightElbow.bone.Magnitude,
		},
	}, R15Rig)
	return self :: any
end

function R15Rig.setRootCF(self: Rig, cf: CFrame)
	self.rootCF = cf
end

-- Transform tablosundan tüm parçaların dünya CFrame'ini hesapla (eksik eklem = kimlik)
function R15Rig.forward(self: Rig, transforms: { [string]: CFrame }): { [string]: CFrame }
	local cf = self.partCF
	cf.HumanoidRootPart = self.rootCF
	for _, name in self.order do
		local j = self.joints[name]
		local t = transforms[name] or CFrame.identity
		cf[j.part1] = cf[j.part0] * j.c0 * t * j.c1:Inverse()
	end
	return cf
end

-- Eklemin çözümlemesi için bilgi (IK girişi)
function R15Rig.info(self: Rig, name: string): IK.JointInfo
	local j = self.joints[name]
	return { c0 = j.c0, c1 = j.c1, bone = j.bone }
end

-- Eklem çerçevesi (Part0 tarafı, Transform uygulanmadan): omuz/kalça pivotu
function R15Rig.jointFrame(self: Rig, parts: { [string]: CFrame }, name: string): CFrame
	local j = self.joints[name]
	return parts[j.part0] * j.c0
end

function R15Rig.apply(self: Rig, transforms: { [string]: CFrame })
	for _, name in self.order do
		self.joints[name].motor.Transform = transforms[name] or CFrame.identity
	end
end

function R15Rig.reset(self: Rig)
	for _, name in self.order do
		self.joints[name].motor.Transform = CFrame.identity
	end
end

return R15Rig
]===])
mk(F_Rig, "ModuleScript", "RigPrep", [===[
--!strict
--[[
	Rig hazırlığı (idempotent): karakteri prosedürel animasyona hazır hale getirir. Modelin geometrisini/Motor6D'lerini
	DEĞİŞTİRMEZ; yalnızca animasyonu bozacak şeyleri kapatır:
	  - HumanoidRootPart anchored, diğer parçalar unanchored (Motor6D zinciri kökten taşınır; hepsi anchored olursa
	    Transform görsel olarak uygulanmaz)
	  - varsayılan "Animate" scripti ve çalan AnimationTrack'ler durur (Motor6D.Transform'u ezmesinler)
	  - Humanoid durum makinesi kapalı (düşme/yürüme animasyonu çıkmasın)
]]

local RigPrep = {}

function RigPrep.prepare(model: Model)
	local hrp = model:FindFirstChild("HumanoidRootPart", true) :: any
	if hrp then
		hrp.Anchored = true
	end
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") and d ~= hrp then
			local bp: any = d
			bp.Anchored = false
			bp.CanCollide = false
		elseif d:IsA("LocalScript") or d:IsA("Script") then
			if d.Name == "Animate" then
				local sc: any = d
				sc.Disabled = true
			end
		end
	end
	local hum = model:FindFirstChildOfClass("Humanoid") :: any
	if hum then
		hum.WalkSpeed = 0
		hum.JumpPower = 0
		hum.AutoRotate = false
		hum.EvaluateStateMachine = false
		hum.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
		local animator = hum:FindFirstChildOfClass("Animator") :: any
		if animator then
			for _, track in animator:GetPlayingAnimationTracks() do
				track:Stop(0)
			end
		end
	end
end

return RigPrep
]===])
mk(F_Rig, "ModuleScript", "TwoBoneIK", [===[
--!strict
--[[
	Analitik iki kemikli IK (omuz-dirsek-bilek / kalça-diz-ayak bileği) + eksen-çevirme (twist) çözümü.

	Motor6D kemiklerine DOĞRUDAN Transform yazar; IKControl'e bağımlı değildir (deterministik, test edilebilir,
	her karede aynı sonuç). IKControl'ün çözdüğü şeyi burada kendimiz çözüyoruz çünkü:
	  1) dirseğin/dizin MENTEŞE ekseni anatomik olmalı (twist'i kol düzlemine göre çözeriz),
	  2) hedefe ulaşılamazsa yumuşak (soft) uzama yapıp "pop" olmasını engellemek istiyoruz,
	  3) FK ile ağırlıklı karıştırma (IK weight) gerekiyor.

	Çözüm yalnızca CFrame cebiri kullanır: eklem çerçeveleri (C0/C1) ne olursa olsun çalışır, bone vektörü
	`C1⁻¹ * çocukEklem.C0.Position` ile eklem uzayından okunur.
]]

export type JointInfo = {
	c0: CFrame,
	c1: CFrame,
	bone: Vector3, -- bu eklemden çocuk eklemine, EKLEM uzayında vektör (uç eklemde sıfır)
}

local IK = {}

local function perpTo(v: Vector3, axis: Vector3): Vector3
	local p = v - axis * v:Dot(axis)
	if p.Magnitude < 1e-4 then
		-- dejenere: eksene dik herhangi bir yön
		local alt = math.abs(axis.Y) < 0.9 and Vector3.new(0, 1, 0) or Vector3.new(1, 0, 0)
		p = alt - axis * alt:Dot(axis)
	end
	return p.Unit
end

-- a'dan b'ye en küçük dönüş (saf rotasyon CFrame)
function IK.rotFromTo(a: Vector3, b: Vector3): CFrame
	local axis = a:Cross(b)
	local s = axis.Magnitude
	local c = a:Dot(b)
	if s < 1e-7 then
		if c > 0 then
			return CFrame.identity
		end
		return CFrame.fromAxisAngle(perpTo(Vector3.new(0, 1, 0), a), math.pi)
	end
	return CFrame.fromAxisAngle(axis / s, math.atan2(s, c))
end

--[[
	Ekleme konumunu bul. Dönüş: dirsek/diz dünya konumu, gerçekte ulaşılan uç konumu, kol düzlemi yönü.
	soft: tam uzamaya yaklaşırken yumuşatma payı (stud). Hedef erişilemezse uç hedefe doğru uzar ama geçmez.
]]
function IK.solvePositions(root: Vector3, target: Vector3, l1: number, l2: number, pole: Vector3, soft: number?)
	local toT = target - root
	local dist = toT.Magnitude
	local maxR = l1 + l2
	local dir = dist > 1e-6 and toT / dist or Vector3.new(0, -1, 0)
	local d = dist
	local s = soft or 0
	if s > 0 and d > maxR - s then
		d = (maxR - s) + s * (1 - math.exp(-(d - (maxR - s)) / s))
	end
	d = math.clamp(d, math.abs(l1 - l2) + 1e-3, maxR - 1e-4)
	local along = (d * d + l1 * l1 - l2 * l2) / (2 * d)
	local h = math.sqrt(math.max(l1 * l1 - along * along, 0))
	local pp = perpTo(pole, dir)
	return root + dir * along + pp * h, root + dir * d, pp
end

export type ChainResult = {
	t1: CFrame, -- 1. eklem (omuz/kalça) Transform
	t2: CFrame, -- 2. eklem (dirsek/diz) Transform
	t3: CFrame, -- 3. eklem (bilek/ayak bileği) Transform
	cf1: CFrame, -- 1. kemiğin (üst kol/üst bacak) dünya CFrame'i
	cf2: CFrame, -- 2. kemiğin (ön kol/alt bacak) dünya CFrame'i
	cf3: CFrame, -- uç parça (el/ayak) dünya CFrame'i
	reachError: number, -- uç eklem hedefine kalan mesafe (stud)
}

--[[
	parentCF : 1. eklemin Part0 dünya CFrame'i (UpperTorso / LowerTorso)
	j1,j2,j3 : omuz/dirsek/bilek (ya da kalça/diz/ayak bileği) eklem bilgileri
	endCF    : uç parçanın (Hand/Foot) istenen DÜNYA CFrame'i (bilek yönü burada belirlenir)
	pole     : dirseğin/dizin döneceği yön (dünya) - dirsek dışa-aşağı, diz öne
	flexSign : +1 dirsek (X ekseninde pozitif döndürme = öne bükme), -1 diz (geriye bükme)
]]
function IK.solveChain(
	parentCF: CFrame,
	j1: JointInfo,
	j2: JointInfo,
	j3: JointInfo,
	endCF: CFrame,
	pole: Vector3,
	flexSign: number,
	soft: number?,
	rootOffset: Vector3?, -- omuz/kalça eklemini Part0'a göre kaydır (klavikula/shrug); eklem uzayında
	rollShare: number? -- uç yönelimin ön kol EKSENİ etrafındaki bükülmesinin (pronasyon/supinasyon) ön koldaki payı
): ChainResult
	local F0 = parentCF * j1.c0
	local rootPos = (F0 * (rootOffset or Vector3.zero))
	local l1 = j1.bone.Magnitude
	local l2 = j2.bone.Magnitude
	-- istenen bilek eklemi konumu: uç parçanın C1 noktası
	local wristTarget = (endCF * j3.c1).Position
	local elbowPos, wristPos, pp = IK.solvePositions(rootPos, wristTarget, l1, l2, pole, soft)

	-- 1) omuz: kemik yönü rest -> hedef (swing)
	local d0 = F0:VectorToWorldSpace(j1.bone).Unit
	local u = (elbowPos - rootPos).Unit
	local swing = IK.rotFromTo(d0, u)
	local R1 = swing * F0.Rotation
	-- 2) twist: dirsek menteşe ekseni, kol düzlemi normaline otursun (anatomik menteşe)
	local UA0 = CFrame.new(rootPos) * R1 * j1.c1:Inverse()
	local hinge = (UA0 * j2.c0):VectorToWorldSpace(Vector3.new(flexSign, 0, 0))
	local dir = (wristPos - rootPos).Unit
	local nw = pp:Cross(dir)
	local a = perpTo(hinge, u)
	local n = perpTo(nw, u)
	local theta = math.atan2(u:Dot(a:Cross(n)), a:Dot(n))
	local Fs = CFrame.new(rootPos) * (CFrame.fromAxisAngle(u, theta) * R1)
	local t1 = F0:Inverse() * Fs -- dönüş + (varsa) omuz kayması
	local cf1 = Fs * j1.c1:Inverse()

	-- 3) dirsek: ön kol yönü
	local Fe0 = cf1 * j2.c0
	local ePos = Fe0.Position
	local d0e = Fe0:VectorToWorldSpace(j2.bone).Unit
	local de = (wristPos - ePos).Unit
	local Fe = CFrame.new(ePos) * (IK.rotFromTo(d0e, de) * Fe0.Rotation)
	-- 3b) ön kol rolü: istenen el yönelimi ön kolun ekseni etrafında dönmüş olabilir (avuç içi yönü). Gerçek kolda bu
	--     dönüş çoğunlukla ÖN KOLDA (pronasyon) olur, bilekte değil; payı kadarını burada ön kola ver.
	local share = rollShare or 0
	if share > 0 then
		local Fw0 = (Fe * j2.c1:Inverse()) * j3.c0
		local rel = Fw0:Inverse() * endCF * j3.c1 -- bilek eklemindeki gereken dönüş
		local axisW = de
		local axisLocal = Fw0:VectorToObjectSpace(axisW)
		local qaxis, qang = rel:ToAxisAngle()
		-- twist = açının eksen üzerindeki izdüşümü (swing-twist ayrıştırması)
		local twist = qang * qaxis:Dot(axisLocal)
		local roll = math.clamp(twist * share, -math.rad(100), math.rad(100))
		Fe = CFrame.fromAxisAngle(axisW, roll) * Fe.Rotation + Fe.Position
		-- not: Fe.Rotation CFrame'i pozisyonsuz; yukarıdaki çarpım ve toplama konumu korur
	end
	local t2 = (Fe0:Inverse() * Fe).Rotation
	local cf2 = Fe * j2.c1:Inverse()

	-- 4) bilek: uç parça tam istenen yönelimde
	local Fw = cf2 * j3.c0
	local t3 = (Fw:Inverse() * endCF * j3.c1).Rotation
	local cf3 = Fw * t3 * j3.c1:Inverse()
	return {
		t1 = t1, t2 = t2, t3 = t3,
		cf1 = cf1, cf2 = cf2, cf3 = cf3,
		reachError = (wristTarget - Fw.Position).Magnitude,
	}
end

-- Dönüş açısını sınırla (bilek/ayak bileği için güvenlik): eksen-açı ayrıştırmasıyla açıyı kısar.
function IK.limitRotation(rot: CFrame, maxAngle: number): CFrame
	local axis, angle = rot:ToAxisAngle()
	if angle <= maxAngle then
		return rot
	end
	return CFrame.fromAxisAngle(axis, maxAngle)
end

return IK
]===])
mk(SSS, "Script", "BandServer", [===[
--!strict
--[[
	SUNUCU: yalnızca "ne zaman ve hangi karakterler" sorumluluğu.
	  - R15 karakterleri bulur ve animasyona hazırlar (HRP anchored, Animate kapalı) - idempotent
	  - ortak şarkı başlangıç zamanını (sunucu saati) workspace attribute'una yazar; şarkı bitince (isteğe bağlı) tekrar başlatır
	Sunucu Motor6D yazmaz: Transform replike olmaz, her istemci animasyonu aynı saatten KENDİ üretir (BandClient).
	Bu yüzden ağ trafiği yok, gecikme yok, herkes aynı karede aynı vuruşu görür.

	Ayarlar (workspace attribute): BandLoop (bool, varsayılan true), BandLeadIn (sn, varsayılan 3; BandRecord açıkken 6),
	BandSongId (rbxassetid://...), BandRecord (bool: sessiz kayıt modu, geri sayım + flaş, döngü kapalı)
]]

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local BandPerformance = require(ReplicatedStorage:WaitForChild("BandPerformance"))
local RigPrep = require(ReplicatedStorage.BandPerformance.Rig.RigPrep)
local Config = BandPerformance.Config
local Song = require(ReplicatedStorage.BandPerformance.Data.SongMap)

local container: Instance = workspace:FindFirstChild("Band") or workspace

for _, e in BandPerformance.discover(container) do
	RigPrep.prepare(e.model)
end

if workspace:GetAttribute("BandLoop") == nil then
	workspace:SetAttribute("BandLoop", true)
end
local recording = workspace:GetAttribute("BandRecord") == true
if recording then
	workspace:SetAttribute("BandLoop", false)
end
local leadIn = workspace:GetAttribute("BandLeadIn")
if type(leadIn) ~= "number" then
	leadIn = recording and 6 or 3
end

local function schedule()
	workspace:SetAttribute(Config.START_ATTRIBUTE, workspace:GetServerTimeNow() + (leadIn :: number))
end

schedule()
task.spawn(function()
	while true do
		task.wait(1)
		local start = workspace:GetAttribute(Config.START_ATTRIBUTE)
		if type(start) == "number" and workspace:GetServerTimeNow() - start > Song.duration + 1.5 then
			if workspace:GetAttribute("BandLoop") then
				schedule()
			else
				workspace:SetAttribute(Config.START_ATTRIBUTE, nil)
			end
		end
	end
end)
]===])
mk(SPS, "LocalScript", "BandClient", [===[
--!strict
--[[
	İSTEMCİ: animasyonun asıl üretildiği yer (Motor6D.Transform + prop CFrame'leri yalnızca yerelde yazılır).
	  - saat: sunucunun yazdığı başlangıç zamanı (herkes aynı karede)
	  - ses: yerel Sound, sunucu saatine göre başlatılır ve kayma >0.12 sn ise düzeltilir (animasyon sese değil SAATE kilitli;
	    ses saate yaklaştırılır) -> ses gecikmesi için Config.VISUAL_LEAD
	  - güncelleme RenderStep'te, kameradan ÖNCE: Roblox'un animasyon güncellemesinden sonra yazdığımız için Animator ezmez
	Kamera: workspace attribute "BandCamera" = "auto" | "front" | "guitarSide" | ... (boşsa kamera kullanıcıda kalır)
	Hata ayıklama: workspace attribute "BandDebug" = true -> 5 sn'de bir temas hatası/duruş özeti
]]

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local SoundService = game:GetService("SoundService")

local BandPerformance = require(ReplicatedStorage:WaitForChild("BandPerformance"))
local Config = BandPerformance.Config
local Song = require(ReplicatedStorage.BandPerformance.Data.SongMap)

local container: Instance = workspace:FindFirstChild("Band") or workspace
local band = BandPerformance.new({
	container = container,
	timeSource = BandPerformance.serverTimeSource(workspace),
	buildProps = true,
	propsParent = workspace,
	getCameraPosition = function()
		local cam = workspace.CurrentCamera
		return cam and cam.CFrame.Position or nil
	end,
})

-- ── ses
local sound: Sound? = (workspace:FindFirstChild(Config.SOUND_NAME) or SoundService:FindFirstChild(Config.SOUND_NAME)) :: any
if sound == nil then
	local id = workspace:GetAttribute("BandSongId")
	if type(id) == "string" and id ~= "" then
		local s = Instance.new("Sound")
		s.Name = Config.SOUND_NAME
		s.SoundId = id
		s.Looped = false
		s.Parent = SoundService
		sound = s
	end
end

local function syncSound()
	if sound == nil then
		return
	end
	local start = workspace:GetAttribute(Config.START_ATTRIBUTE)
	if type(start) ~= "number" then
		if sound.IsPlaying then
			sound:Stop()
		end
		return
	end
	local t = workspace:GetServerTimeNow() - start
	if t < 0 or t > Song.duration then
		if sound.IsPlaying and t > Song.duration then
			sound:Stop()
		end
		return
	end
	if not sound.IsPlaying then
		sound.TimePosition = t
		sound:Play()
	elseif math.abs(sound.TimePosition - t) > 0.12 then
		sound.TimePosition = t
	end
end

-- ── kamera
local cameraRig = BandPerformance.CameraRig.new()
local cameraMode: string? = nil
local function applyCameraMode()
	local mode = workspace:GetAttribute("BandCamera")
	if mode == true then
		mode = "auto" -- Boolean işaretlenmişse otomatik yönetmen
	end
	if type(mode) == "string" and mode ~= "" then
		mode = string.lower(mode)
		if mode ~= "auto" and BandPerformance.CameraRig.resolve(mode) == nil then
			warn("[Band] Bilinmeyen BandCamera: '" .. mode .. "' -> auto kullanılıyor")
			mode = "auto"
		end
		if mode ~= cameraMode then
			cameraMode = mode
			workspace.CurrentCamera.CameraType = Enum.CameraType.Scriptable
			if mode ~= "auto" then
				cameraRig:cut(mode, band)
			end
		end
	elseif cameraMode ~= nil then
		cameraMode = nil
		workspace.CurrentCamera.CameraType = Enum.CameraType.Custom
	end
end

-- ── kayıt modu: sessiz çalış, geri sayım + senkron flaşı (video editöründe mp3'ü bu flaşa hizala)
-- workspace attribute BandRecord = true  ->  ekranda 3-2-1 geri sayımı, şarkı zamanı 0'da tek karelik beyaz flaş
local Players = game:GetService("Players")
local gui: ScreenGui? = nil
local label: TextLabel? = nil
local flash: Frame? = nil
local function ensureGui()
	if gui then
		return
	end
	local g = Instance.new("ScreenGui")
	g.Name = "BandRecordOverlay"
	g.IgnoreGuiInset = true
	g.ResetOnSpawn = false
	g.Parent = Players.LocalPlayer:WaitForChild("PlayerGui")
	local l = Instance.new("TextLabel")
	l.Size = UDim2.fromScale(1, 0.3)
	l.Position = UDim2.fromScale(0, 0.35)
	l.BackgroundTransparency = 1
	l.TextScaled = true
	l.Font = Enum.Font.GothamBlack
	l.TextColor3 = Color3.new(1, 1, 1)
	l.TextStrokeTransparency = 0
	l.Text = ""
	l.Parent = g
	local f = Instance.new("Frame")
	f.Size = UDim2.fromScale(1, 1)
	f.BackgroundColor3 = Color3.new(1, 1, 1)
	f.BackgroundTransparency = 1
	f.BorderSizePixel = 0
	f.Parent = g
	gui, label, flash = g, l, f
end
local lastFlashed = false
local function updateRecordOverlay()
	if not workspace:GetAttribute("BandRecord") then
		if gui then
			gui.Enabled = false
		end
		return
	end
	ensureGui()
	;(gui :: ScreenGui).Enabled = true
	local start = workspace:GetAttribute(Config.START_ATTRIBUTE)
	local lbl, fl = label :: TextLabel, flash :: Frame
	if type(start) ~= "number" then
		lbl.Text = ""
		return
	end
	local t = workspace:GetServerTimeNow() - start
	if t < 0 then
		lbl.Text = tostring(math.ceil(-t))
		fl.BackgroundTransparency = 1
		lastFlashed = false
	else
		lbl.Text = ""
		-- şarkı zamanı 0..0.1 sn: beyaz flaş (sonra söner)
		fl.BackgroundTransparency = (t < 0.1) and 0 or 1
	end
end

local debugT = 0
RunService:BindToRenderStep("BandPerformanceUpdate", Enum.RenderPriority.Camera.Value - 1, function(dt)
	syncSound()
	band:update(dt)
	applyCameraMode()
	updateRecordOverlay()
	if cameraMode ~= nil then
		if cameraMode == "auto" then
			cameraRig:direct(band)
		end
		workspace.CurrentCamera.CFrame = cameraRig:update(dt, band)
	end
	if workspace:GetAttribute("BandDebug") then
		debugT += dt
		if debugT > 5 then
			debugT = 0
			for role, m in band:getMetrics() do
				print(string.format("[Band] %-6s %-10s elHata L%.3f R%.3f", role, m.state, m.handError.Left, m.handError.Right))
			end
		end
	end
end)
]===])
print("BandPerformance kuruldu. workspace.Band klasörüne karakterleri koy, BandRecord = true yap, Play.")
