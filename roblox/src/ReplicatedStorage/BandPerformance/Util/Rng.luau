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
