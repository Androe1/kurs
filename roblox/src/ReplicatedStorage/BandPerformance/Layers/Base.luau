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
