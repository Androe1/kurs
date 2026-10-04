--!strict
--[[
	Analitik iki kemikli IK (omuz-dirsek-bilek / kalça-diz-ayak bileği) + eksen-çevirme (twist) çözümü.

	Motor6D kemiklerine DOĞRUDAN Transform yazar; IKControl'e bağımlı değildir (deterministik, test edilebilir,
	her karede aynı sonuç). IKControl'ün çözdüğü şeyi burada kendimiz çözüyoruz çünkü:
	  1) dirseğin/dizin MENTEŞE ekseni anatomik olmalı (twist'i kol düzlemine göre çözeriz),
	  2) hedefe ulaşılamazsa yumuşak (soft) uzama yapıp "pop" olmasını engellemek istiyoruz,
	  3) FK ile ağırlıklı karıştırma (IK weight) gerekiyor.

	Çözüm yalnızca CFrame cebiri kullanır: eklem çerçeveleri (C0/C1) ne olursa olsun çalışır, bone vektörü
	`C1⁻¹ * çocukEklem.C0.Position` ile eklem uzayından okunur.
]]

export type JointInfo = {
	c0: CFrame,
	c1: CFrame,
	bone: Vector3, -- bu eklemden çocuk eklemine, EKLEM uzayında vektör (uç eklemde sıfır)
}

local IK = {}

local function perpTo(v: Vector3, axis: Vector3): Vector3
	local p = v - axis * v:Dot(axis)
	if p.Magnitude < 1e-4 then
		-- dejenere: eksene dik herhangi bir yön
		local alt = math.abs(axis.Y) < 0.9 and Vector3.new(0, 1, 0) or Vector3.new(1, 0, 0)
		p = alt - axis * alt:Dot(axis)
	end
	return p.Unit
end

-- a'dan b'ye en küçük dönüş (saf rotasyon CFrame)
function IK.rotFromTo(a: Vector3, b: Vector3): CFrame
	local axis = a:Cross(b)
	local s = axis.Magnitude
	local c = a:Dot(b)
	if s < 1e-7 then
		if c > 0 then
			return CFrame.identity
		end
		return CFrame.fromAxisAngle(perpTo(Vector3.new(0, 1, 0), a), math.pi)
	end
	return CFrame.fromAxisAngle(axis / s, math.atan2(s, c))
end

--[[
	Ekleme konumunu bul. Dönüş: dirsek/diz dünya konumu, gerçekte ulaşılan uç konumu, kol düzlemi yönü.
	soft: tam uzamaya yaklaşırken yumuşatma payı (stud). Hedef erişilemezse uç hedefe doğru uzar ama geçmez.
]]
function IK.solvePositions(root: Vector3, target: Vector3, l1: number, l2: number, pole: Vector3, soft: number?)
	local toT = target - root
	local dist = toT.Magnitude
	local maxR = l1 + l2
	local dir = dist > 1e-6 and toT / dist or Vector3.new(0, -1, 0)
	local d = dist
	local s = soft or 0
	if s > 0 and d > maxR - s then
		d = (maxR - s) + s * (1 - math.exp(-(d - (maxR - s)) / s))
	end
	d = math.clamp(d, math.abs(l1 - l2) + 1e-3, maxR - 1e-4)
	local along = (d * d + l1 * l1 - l2 * l2) / (2 * d)
	local h = math.sqrt(math.max(l1 * l1 - along * along, 0))
	local pp = perpTo(pole, dir)
	return root + dir * along + pp * h, root + dir * d, pp
end

export type ChainResult = {
	t1: CFrame, -- 1. eklem (omuz/kalça) Transform
	t2: CFrame, -- 2. eklem (dirsek/diz) Transform
	t3: CFrame, -- 3. eklem (bilek/ayak bileği) Transform
	cf1: CFrame, -- 1. kemiğin (üst kol/üst bacak) dünya CFrame'i
	cf2: CFrame, -- 2. kemiğin (ön kol/alt bacak) dünya CFrame'i
	cf3: CFrame, -- uç parça (el/ayak) dünya CFrame'i
	reachError: number, -- uç eklem hedefine kalan mesafe (stud)
}

--[[
	parentCF : 1. eklemin Part0 dünya CFrame'i (UpperTorso / LowerTorso)
	j1,j2,j3 : omuz/dirsek/bilek (ya da kalça/diz/ayak bileği) eklem bilgileri
	endCF    : uç parçanın (Hand/Foot) istenen DÜNYA CFrame'i (bilek yönü burada belirlenir)
	pole     : dirseğin/dizin döneceği yön (dünya) - dirsek dışa-aşağı, diz öne
	flexSign : +1 dirsek (X ekseninde pozitif döndürme = öne bükme), -1 diz (geriye bükme)
]]
function IK.solveChain(
	parentCF: CFrame,
	j1: JointInfo,
	j2: JointInfo,
	j3: JointInfo,
	endCF: CFrame,
	pole: Vector3,
	flexSign: number,
	soft: number?,
	rootOffset: Vector3?, -- omuz/kalça eklemini Part0'a göre kaydır (klavikula/shrug); eklem uzayında
	rollShare: number? -- uç yönelimin ön kol EKSENİ etrafındaki bükülmesinin (pronasyon/supinasyon) ön koldaki payı
): ChainResult
	local F0 = parentCF * j1.c0
	local rootPos = (F0 * (rootOffset or Vector3.zero))
	local l1 = j1.bone.Magnitude
	local l2 = j2.bone.Magnitude
	-- istenen bilek eklemi konumu: uç parçanın C1 noktası
	local wristTarget = (endCF * j3.c1).Position
	local elbowPos, wristPos, pp = IK.solvePositions(rootPos, wristTarget, l1, l2, pole, soft)

	-- 1) omuz: kemik yönü rest -> hedef (swing)
	local d0 = F0:VectorToWorldSpace(j1.bone).Unit
	local u = (elbowPos - rootPos).Unit
	local swing = IK.rotFromTo(d0, u)
	local R1 = swing * F0.Rotation
	-- 2) twist: dirsek menteşe ekseni, kol düzlemi normaline otursun (anatomik menteşe)
	local UA0 = CFrame.new(rootPos) * R1 * j1.c1:Inverse()
	local hinge = (UA0 * j2.c0):VectorToWorldSpace(Vector3.new(flexSign, 0, 0))
	local dir = (wristPos - rootPos).Unit
	local nw = pp:Cross(dir)
	local a = perpTo(hinge, u)
	local n = perpTo(nw, u)
	local theta = math.atan2(u:Dot(a:Cross(n)), a:Dot(n))
	local Fs = CFrame.new(rootPos) * (CFrame.fromAxisAngle(u, theta) * R1)
	local t1 = F0:Inverse() * Fs -- dönüş + (varsa) omuz kayması
	local cf1 = Fs * j1.c1:Inverse()

	-- 3) dirsek: ön kol yönü
	local Fe0 = cf1 * j2.c0
	local ePos = Fe0.Position
	local d0e = Fe0:VectorToWorldSpace(j2.bone).Unit
	local de = (wristPos - ePos).Unit
	local Fe = CFrame.new(ePos) * (IK.rotFromTo(d0e, de) * Fe0.Rotation)
	-- 3b) ön kol rolü: istenen el yönelimi ön kolun ekseni etrafında dönmüş olabilir (avuç içi yönü). Gerçek kolda bu
	--     dönüş çoğunlukla ÖN KOLDA (pronasyon) olur, bilekte değil; payı kadarını burada ön kola ver.
	local share = rollShare or 0
	if share > 0 then
		local Fw0 = (Fe * j2.c1:Inverse()) * j3.c0
		local rel = Fw0:Inverse() * endCF * j3.c1 -- bilek eklemindeki gereken dönüş
		local axisW = de
		local axisLocal = Fw0:VectorToObjectSpace(axisW)
		local qaxis, qang = rel:ToAxisAngle()
		-- twist = açının eksen üzerindeki izdüşümü (swing-twist ayrıştırması)
		local twist = qang * qaxis:Dot(axisLocal)
		local roll = math.clamp(twist * share, -math.rad(100), math.rad(100))
		Fe = CFrame.fromAxisAngle(axisW, roll) * Fe.Rotation + Fe.Position
		-- not: Fe.Rotation CFrame'i pozisyonsuz; yukarıdaki çarpım ve toplama konumu korur
	end
	local t2 = (Fe0:Inverse() * Fe).Rotation
	local cf2 = Fe * j2.c1:Inverse()

	-- 4) bilek: uç parça tam istenen yönelimde
	local Fw = cf2 * j3.c0
	local t3 = (Fw:Inverse() * endCF * j3.c1).Rotation
	local cf3 = Fw * t3 * j3.c1:Inverse()
	return {
		t1 = t1, t2 = t2, t3 = t3,
		cf1 = cf1, cf2 = cf2, cf3 = cf3,
		reachError = (wristTarget - Fw.Position).Magnitude,
	}
end

-- Dönüş açısını sınırla (bilek/ayak bileği için güvenlik): eksen-açı ayrıştırmasıyla açıyı kısar.
function IK.limitRotation(rot: CFrame, maxAngle: number): CFrame
	local axis, angle = rot:ToAxisAngle()
	if angle <= maxAngle then
		return rot
	end
	return CFrame.fromAxisAngle(axis, maxAngle)
end

return IK
