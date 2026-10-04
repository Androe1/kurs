--!strict
--[[
	Kütleli yay (sönümlü harmonik osilatör), kapalı form çözüm: kare süresinden bağımsız, her dt'de kararlı.
	Bir kemiğin hedef poza "kendiliğinden" gecikmeli, hafifçe aşan ve geç oturan şekilde gitmesini sağlar;
	lead & follow ile overlapping action'ı ayrıca gecikme eklemeden üretir.

	freq   : doğal frekans (Hz)         - yüksek = sert/çevik, düşük = gevşek/ağır
	damping: sönüm oranı ζ               - 1 = kritik, <1 = aşar (overshoot), >1 = ağır sönüm
]]

export type Spring = {
	x: number,
	v: number,
	freq: number,
	damping: number,
}

local Spring = {}
Spring.__index = Spring

function Spring.new(x: number, freq: number, damping: number): Spring
	return setmetatable({ x = x, v = 0, freq = freq, damping = damping }, Spring) :: any
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
export type Spring3 = {
	x: Spring,
	y: Spring,
	z: Spring,
}
local Spring3 = {}
Spring3.__index = Spring3

function Spring3.new(value: Vector3, freq: number, damping: number): Spring3
	return setmetatable({
		x = Spring.new(value.X, freq, damping),
		y = Spring.new(value.Y, freq, damping),
		z = Spring.new(value.Z, freq, damping),
	}, Spring3) :: any
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
