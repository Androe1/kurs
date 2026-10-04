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
