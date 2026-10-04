--!strict
--[[
	Davul seti yerleşimi. Konumlar OTURAN KALÇA merkezine (LowerTorso, oturuş pozunda) göre ve referans erişim 2.2
	stud için yazıldı; rig'in erişimine göre ölçeklenir. +X davulcunun sağı, -Z ileri (set önde).
	Hem animasyon (hedefler) hem PropBuilder (parçalar) aynı tabloyu kullanır -> el ile set hep hizalı.
]]

local DrumKit = {}

export type Piece = {
	name: string,
	kind: string, -- "head" (derili davul) | "cymbal" | "kick" | "hat"
	center: Vector3, -- kalça merkezine göre, referans birim
	radius: number,
	tilt: number, -- yüzey normalinin davulcuya doğru eğimi (rad)
	thickness: number,
}

-- tilt: +: yüzey davulcuya doğru yatık (normal = (0, cos, +sin)), teller/zil hafif eğik
DrumKit.PIECES = {
	snare = { kind = "head", center = Vector3.new(0.00, 0.62, -1.9), radius = 0.42, tilt = math.rad(6), thickness = 0.28 },
	tom1 = { kind = "head", center = Vector3.new(-0.45, 1.0, -2.3), radius = 0.34, tilt = math.rad(24), thickness = 0.3 },
	tom2 = { kind = "head", center = Vector3.new(0.5, 1.0, -2.3), radius = 0.37, tilt = math.rad(22), thickness = 0.32 },
	floor = { kind = "head", center = Vector3.new(1.55, 0.4, -2.05), radius = 0.5, tilt = math.rad(4), thickness = 0.55 },
	hat = { kind = "hat", center = Vector3.new(-1.0, 0.95, -1.7), radius = 0.4, tilt = math.rad(6), thickness = 0.06 },
	crash = { kind = "cymbal", center = Vector3.new(-1.75, 1.55, -2.7), radius = 0.55, tilt = math.rad(18), thickness = 0.05 },
	ride = { kind = "cymbal", center = Vector3.new(1.95, 1.3, -2.6), radius = 0.62, tilt = math.rad(12), thickness = 0.05 },
	kick = { kind = "kick", center = Vector3.new(0.12, 0.35, -3.0), radius = 0.8, tilt = 0, thickness = 0.9 },
}

-- ayak pedalları (ayak bileği hedef konumu, kalça merkezine göre): sağ = kick pedalı, sol = hi-hat pedalı
DrumKit.PEDALS = {
	Right = Vector3.new(0.38, -1.34, -1.55),
	Left = Vector3.new(-0.72, -1.38, -1.25),
}

--[[ rig + sahne CFrame'i (HRP) için dünya yerleşimi. seatDrop: kalçanın dinlenme duruşuna göre alçalması (üst bacak boyu)
	Dönüş: parça adı -> { pos, normal, radius, kind, up(rel) }, pedallar, orijin (oturan kalça merkezi) ]]
function DrumKit.layout(rig: any, stage: CFrame)
	local s = rig.lengths.reach / 2.2
	local seatDrop = rig.lengths.legUpper
	-- dinlenme duruşunda kalça merkezi = HRP (LowerTorso) kök; otururken seatDrop kadar aşağıda
	local lt = rig.joints.Root
	local origin = stage * lt.c0 * Vector3.new(0, -seatDrop, 0)
	local out = {}
	for name, p in DrumKit.PIECES do
		local c = stage:VectorToWorldSpace(p.center * s) + origin
		local n = stage:VectorToWorldSpace(Vector3.new(0, math.cos(p.tilt), math.sin(p.tilt)))
		out[name] = { name = name, kind = p.kind, pos = c, normal = n, radius = p.radius * s, thickness = p.thickness * s, tilt = p.tilt }
	end
	local pedals = {}
	for side, v in DrumKit.PEDALS do
		pedals[side] = stage:VectorToWorldSpace(v * s) + origin
	end
	return { pieces = out, pedals = pedals, origin = origin, scale = s, seatDrop = seatDrop }
end

return DrumKit
