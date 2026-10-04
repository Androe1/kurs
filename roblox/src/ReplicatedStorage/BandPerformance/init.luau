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
	for _, role in self.order do
		self.performers[role]:update(dt)
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
