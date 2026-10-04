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
