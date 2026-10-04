--!nonstrict
--[[
	Roblox veri tiplerinin (Vector3, CFrame, Instance, Enum benzeri) saf Luau taklidi.
	Amaç: BandPerformance çekirdeğini (yaylar, IK, ritim, katmanlar) Roblox Studio olmadan
	gerçek bir Luau VM'inde çalıştırıp doğrulamak. Yalnızca çekirdeğin kullandığı yüzey vardır.
	Roblox'taki anlamlarıyla aynıdır: sağ el koordinatı, karakter -Z'ye bakar, +X karakterin sağıdır.
]]

local Rbx = {}

-- ───────────── Vector3 ─────────────
local V3 = {}
V3.__index = function(t, k)
	if k == "Magnitude" then
		return math.sqrt(t.X * t.X + t.Y * t.Y + t.Z * t.Z)
	elseif k == "Unit" then
		local m = math.sqrt(t.X * t.X + t.Y * t.Y + t.Z * t.Z)
		if m == 0 then return setmetatable({ X = 0, Y = 0, Z = 0 }, V3) end
		return setmetatable({ X = t.X / m, Y = t.Y / m, Z = t.Z / m }, V3)
	end
	return V3[k]
end
local function v3(x, y, z) return setmetatable({ X = x, Y = y, Z = z }, V3) end
V3.__add = function(a, b) return v3(a.X + b.X, a.Y + b.Y, a.Z + b.Z) end
V3.__sub = function(a, b) return v3(a.X - b.X, a.Y - b.Y, a.Z - b.Z) end
V3.__unm = function(a) return v3(-a.X, -a.Y, -a.Z) end
V3.__mul = function(a, b)
	if type(a) == "number" then return v3(a * b.X, a * b.Y, a * b.Z) end
	if type(b) == "number" then return v3(a.X * b, a.Y * b, a.Z * b) end
	return v3(a.X * b.X, a.Y * b.Y, a.Z * b.Z)
end
V3.__div = function(a, b)
	if type(b) == "number" then return v3(a.X / b, a.Y / b, a.Z / b) end
	return v3(a.X / b.X, a.Y / b.Y, a.Z / b.Z)
end
V3.__eq = function(a, b) return a.X == b.X and a.Y == b.Y and a.Z == b.Z end
V3.__tostring = function(a) return string.format("%.3f, %.3f, %.3f", a.X, a.Y, a.Z) end
function V3:Dot(o) return self.X * o.X + self.Y * o.Y + self.Z * o.Z end
function V3:Cross(o)
	return v3(self.Y * o.Z - self.Z * o.Y, self.Z * o.X - self.X * o.Z, self.X * o.Y - self.Y * o.X)
end
function V3:Lerp(o, a) return self + (o - self) * a end
function V3:FuzzyEq(o, e) return (self - o).Magnitude <= (e or 1e-5) end
local Vector3 = {
	new = function(x, y, z) return v3(x or 0, y or 0, z or 0) end,
	zero = v3(0, 0, 0), one = v3(1, 1, 1),
	xAxis = v3(1, 0, 0), yAxis = v3(0, 1, 0), zAxis = v3(0, 0, 1),
}
Rbx.Vector3 = Vector3

-- ───────────── CFrame ─────────────
local CF = {}
local function mk(p, r00, r01, r02, r10, r11, r12, r20, r21, r22)
	return setmetatable({ p = p, r00 = r00, r01 = r01, r02 = r02, r10 = r10, r11 = r11, r12 = r12, r20 = r20, r21 = r21, r22 = r22 }, CF)
end
CF.__index = function(t, k)
	if k == "Position" then return t.p
	elseif k == "X" then return t.p.X elseif k == "Y" then return t.p.Y elseif k == "Z" then return t.p.Z
	elseif k == "RightVector" then return v3(t.r00, t.r10, t.r20)
	elseif k == "UpVector" then return v3(t.r01, t.r11, t.r21)
	elseif k == "LookVector" then return v3(-t.r02, -t.r12, -t.r22)
	elseif k == "Rotation" then return mk(v3(0, 0, 0), t.r00, t.r01, t.r02, t.r10, t.r11, t.r12, t.r20, t.r21, t.r22)
	end
	return CF[k]
end
CF.__mul = function(a, b)
	if getmetatable(b) == V3 then
		return v3(
			a.r00 * b.X + a.r01 * b.Y + a.r02 * b.Z + a.p.X,
			a.r10 * b.X + a.r11 * b.Y + a.r12 * b.Z + a.p.Y,
			a.r20 * b.X + a.r21 * b.Y + a.r22 * b.Z + a.p.Z
		)
	end
	local p = a * b.p
	return mk(
		p,
		a.r00 * b.r00 + a.r01 * b.r10 + a.r02 * b.r20, a.r00 * b.r01 + a.r01 * b.r11 + a.r02 * b.r21, a.r00 * b.r02 + a.r01 * b.r12 + a.r02 * b.r22,
		a.r10 * b.r00 + a.r11 * b.r10 + a.r12 * b.r20, a.r10 * b.r01 + a.r11 * b.r11 + a.r12 * b.r21, a.r10 * b.r02 + a.r11 * b.r12 + a.r12 * b.r22,
		a.r20 * b.r00 + a.r21 * b.r10 + a.r22 * b.r20, a.r20 * b.r01 + a.r21 * b.r11 + a.r22 * b.r21, a.r20 * b.r02 + a.r21 * b.r12 + a.r22 * b.r22
	)
end
CF.__add = function(a, v) return mk(a.p + v, a.r00, a.r01, a.r02, a.r10, a.r11, a.r12, a.r20, a.r21, a.r22) end
CF.__sub = function(a, v) return mk(a.p - v, a.r00, a.r01, a.r02, a.r10, a.r11, a.r12, a.r20, a.r21, a.r22) end
function CF:Inverse()
	local ip = v3(
		-(self.r00 * self.p.X + self.r10 * self.p.Y + self.r20 * self.p.Z),
		-(self.r01 * self.p.X + self.r11 * self.p.Y + self.r21 * self.p.Z),
		-(self.r02 * self.p.X + self.r12 * self.p.Y + self.r22 * self.p.Z)
	)
	return mk(ip, self.r00, self.r10, self.r20, self.r01, self.r11, self.r21, self.r02, self.r12, self.r22)
end
function CF:VectorToWorldSpace(v)
	return v3(self.r00 * v.X + self.r01 * v.Y + self.r02 * v.Z, self.r10 * v.X + self.r11 * v.Y + self.r12 * v.Z, self.r20 * v.X + self.r21 * v.Y + self.r22 * v.Z)
end
function CF:VectorToObjectSpace(v) return self:Inverse():VectorToWorldSpace(v) end
function CF:PointToWorldSpace(v) return self * v end
function CF:PointToObjectSpace(v) return self:Inverse() * v end
function CF:ToObjectSpace(o) return self:Inverse() * o end
function CF:ToWorldSpace(o) return self * o end
function CF:GetComponents()
	return self.p.X, self.p.Y, self.p.Z, self.r00, self.r01, self.r02, self.r10, self.r11, self.r12, self.r20, self.r21, self.r22
end

-- döndürmeyi (kuvaterniyon) eksen-açıya çevir
local function toQuat(c)
	local tr = c.r00 + c.r11 + c.r22
	local w, x, y, z
	if tr > 0 then
		local s = math.sqrt(tr + 1) * 2
		w = 0.25 * s; x = (c.r21 - c.r12) / s; y = (c.r02 - c.r20) / s; z = (c.r10 - c.r01) / s
	elseif c.r00 > c.r11 and c.r00 > c.r22 then
		local s = math.sqrt(1 + c.r00 - c.r11 - c.r22) * 2
		w = (c.r21 - c.r12) / s; x = 0.25 * s; y = (c.r01 + c.r10) / s; z = (c.r02 + c.r20) / s
	elseif c.r11 > c.r22 then
		local s = math.sqrt(1 + c.r11 - c.r00 - c.r22) * 2
		w = (c.r02 - c.r20) / s; x = (c.r01 + c.r10) / s; y = 0.25 * s; z = (c.r12 + c.r21) / s
	else
		local s = math.sqrt(1 + c.r22 - c.r00 - c.r11) * 2
		w = (c.r10 - c.r01) / s; x = (c.r02 + c.r20) / s; y = (c.r12 + c.r21) / s; z = 0.25 * s
	end
	return w, x, y, z
end
local function fromQuat(p, w, x, y, z)
	local n = math.sqrt(w * w + x * x + y * y + z * z)
	w, x, y, z = w / n, x / n, y / n, z / n
	return mk(p,
		1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w),
		2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w),
		2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y))
end
function CF:ToAxisAngle()
	local w, x, y, z = toQuat(self)
	if w < 0 then w, x, y, z = -w, -x, -y, -z end
	local s = math.sqrt(x * x + y * y + z * z)
	if s < 1e-9 then return v3(1, 0, 0), 0 end
	return v3(x / s, y / s, z / s), 2 * math.atan2(s, w)
end
function CF:Lerp(o, a)
	local w1, x1, y1, z1 = toQuat(self)
	local w2, x2, y2, z2 = toQuat(o)
	if w1 * w2 + x1 * x2 + y1 * y2 + z1 * z2 < 0 then w2, x2, y2, z2 = -w2, -x2, -y2, -z2 end
	local p = self.p:Lerp(o.p, a)
	-- nlerp (küçük açılarda slerp'e eşdeğer; test için yeterli)
	return fromQuat(p, w1 + (w2 - w1) * a, x1 + (x2 - x1) * a, y1 + (y2 - y1) * a, z1 + (z2 - z1) * a)
end
function CF:ToEulerAnglesYXZ()
	local x = math.asin(-math.clamp(self.r12, -1, 1))
	local y, z
	if math.abs(self.r12) < 0.99999 then
		y = math.atan2(self.r02, self.r22)
		z = math.atan2(self.r10, self.r11)
	else
		y = math.atan2(-self.r20, self.r00); z = 0
	end
	return x, y, z
end
function CF:ToOrientation() return self:ToEulerAnglesYXZ() end

local I = mk(v3(0, 0, 0), 1, 0, 0, 0, 1, 0, 0, 0, 1)
local function rotX(a) local c, s = math.cos(a), math.sin(a) return mk(v3(0, 0, 0), 1, 0, 0, 0, c, -s, 0, s, c) end
local function rotY(a) local c, s = math.cos(a), math.sin(a) return mk(v3(0, 0, 0), c, 0, s, 0, 1, 0, -s, 0, c) end
local function rotZ(a) local c, s = math.cos(a), math.sin(a) return mk(v3(0, 0, 0), c, -s, 0, s, c, 0, 0, 0, 1) end

local CFrame = {
	identity = I,
	new = function(a, b, c)
		if a == nil then return I end
		if type(a) == "table" and getmetatable(a) == V3 then
			if b and getmetatable(b) == V3 then -- CFrame.new(pos, lookAt)
				return Rbx.CFrame.lookAt(a, b)
			end
			return mk(a, 1, 0, 0, 0, 1, 0, 0, 0, 1)
		end
		return mk(v3(a, b, c), 1, 0, 0, 0, 1, 0, 0, 0, 1)
	end,
	fromEulerAnglesXYZ = function(rx, ry, rz) return rotX(rx) * rotY(ry) * rotZ(rz) end,
	fromEulerAnglesYXZ = function(rx, ry, rz) return rotY(ry) * rotX(rx) * rotZ(rz) end,
	fromAxisAngle = function(axis, angle)
		local u = axis.Unit
		local s, c = math.sin(angle / 2), math.cos(angle / 2)
		return fromQuat(v3(0, 0, 0), c, u.X * s, u.Y * s, u.Z * s)
	end,
	fromMatrix = function(pos, vx, vy, vz)
		vz = vz or vx:Cross(vy)
		return mk(pos, vx.X, vy.X, vz.X, vx.Y, vy.Y, vz.Y, vx.Z, vy.Z, vz.Z)
	end,
	lookAt = function(at, lookAt, up)
		up = up or v3(0, 1, 0)
		local back = (at - lookAt).Unit
		local right = up:Cross(back).Unit
		local u = back:Cross(right)
		return Rbx.CFrame.fromMatrix(at, right, u, back)
	end,
}
CFrame.Angles = function(rx, ry, rz) return rotX(rx) * rotY(ry) * rotZ(rz) end
Rbx.CFrame = CFrame
Rbx.CFrameMeta = CF

-- ───────────── Instance / Motor6D / Part / Folder (minimum) ─────────────
local Inst = {}
Inst.__index = function(t, k)
	local m = Inst[k]
	if m ~= nil then return m end
	local kids = rawget(t, "_children")
	if kids then for _, c in ipairs(kids) do if c.Name == k then return c end end end
	return nil
end
function Inst:GetChildren() return self._children end
function Inst:FindFirstChild(name, recursive)
	for _, c in ipairs(self._children) do if c.Name == name then return c end end
	if recursive then
		for _, c in ipairs(self._children) do local f = c:FindFirstChild(name, true) if f then return f end end
	end
	return nil
end
function Inst:FindFirstChildOfClass(cls)
	for _, c in ipairs(self._children) do if c.ClassName == cls then return c end end
	return nil
end
function Inst:FindFirstAncestor(name)
	local p = self.Parent
	while p do if p.Name == name then return p end p = p.Parent end
	return nil
end
function Inst:IsA(cls) return self.ClassName == cls or (cls == "BasePart" and self.ClassName == "Part") end
function Inst:GetDescendants()
	local out = {}
	local function walk(n) for _, c in ipairs(n._children) do table.insert(out, c) walk(c) end end
	walk(self)
	return out
end
function Inst:SetAttribute(k, v) self._attrs[k] = v end
function Inst:GetAttribute(k) return self._attrs[k] end
function Inst:Destroy() end
function Inst:GetPivot() return self.PrimaryPart and self.PrimaryPart.CFrame or self.CFrame or I end
function Inst:PivotTo(cf)
	if self.PrimaryPart then self.PrimaryPart.CFrame = cf else self.CFrame = cf end
end

function Rbx.newInstance(cls, name, props)
	local o = setmetatable({ ClassName = cls, Name = name, _children = {}, _attrs = {} }, Inst)
	for k, v in pairs(props or {}) do o[k] = v end
	return o
end
function Rbx.parent(child, parent)
	child.Parent = parent
	table.insert(parent._children, child)
	return child
end
Rbx.Instance = Inst

return Rbx
