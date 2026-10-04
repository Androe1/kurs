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
