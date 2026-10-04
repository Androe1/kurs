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
