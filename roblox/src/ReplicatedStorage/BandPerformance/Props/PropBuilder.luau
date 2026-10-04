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
