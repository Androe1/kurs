--!strict
--[[
	Etkileşim katmanı: biriken pozdaki el/ayak hedeflerini IK ile çözüp eklem Transform'larına yazar.
	FK (katmanların dönüşleri) ile IK arasında ağırlıkla karıştırır; ağırlık yayla yumuşatılır (snap yok).
	Ayrıca temas hatasını (hedef - gerçek) ölçer: perf.metrics.
]]

local Root = script:FindFirstAncestor("BandPerformance")
local IK = require(Root.Rig.TwoBoneIK)
local Config = require(Root.Config)

local Interaction = {}

local I = CFrame.identity
local SIDES = { "Right", "Left" }

--[[
	Uç noktayı (parmak ucu / ayak bileği) SABİT tutup bilek açısını sınırın içinde bırakır:
	sınır aşılırsa el yönelimi gevşetilir (hedef yönelimden sapar) ama TEMAS NOKTASI kaymaz.
	endPos(handRot) uç parçanın konumunu verir (kavrama ofseti dönmeyle değişir).
]]
local function solveRelaxed(parent: CFrame, j1: any, j2: any, j3: any, rot0: CFrame, endPos: (CFrame) -> Vector3, pole: Vector3, flex: number, soft: number, off: Vector3?, limit: number, roll: number?)
	local rot = rot0
	local res
	for _ = 1, 3 do
		local endCF = CFrame.new(endPos(rot)) * rot
		res = IK.solveChain(parent, j1, j2, j3, endCF, pole, flex, soft, off, roll)
		local axis, ang = res.t3:ToAxisAngle()
		if ang <= limit + 1e-4 then
			return res, res.t3
		end
		local t3c = CFrame.fromAxisAngle(axis, limit)
		local Fw = res.cf2 * j3.c0
		rot = (Fw * t3c * j3.c1:Inverse()).Rotation
	end
	-- son çözüm: gevşetilmiş yönelimle
	local endCF = CFrame.new(endPos(rot)) * rot
	res = IK.solveChain(parent, j1, j2, j3, endCF, pole, flex, soft, off, roll)
	return res, IK.limitRotation(res.t3, limit)
end

local function blend(fk: CFrame?, ik: CFrame, w: number): CFrame
	local f = fk or I
	if w >= 0.999 then
		return ik
	end
	return f:Lerp(ik, w)
end

-- tr: eklem adı -> Transform (iskelet katmanları zaten yazılmış), parts: o ana kadarki FK dünya CFrame'leri
function Interaction.solve(perf: any, pose: any, tr: { [string]: CFrame }, parts: { [string]: CFrame }, dt: number)
	local rig = perf.rig
	local lim = Config.limits
	local metrics = perf.metrics

	-- kollar
	for _, side in SIDES do
		local sh, el, wr = side .. "Shoulder", side .. "Elbow", side .. "Wrist"
		local h = pose.hands[side]
		local w = perf.ikSpring[side]:step(h and h.w or 0, dt)
		w = math.clamp(w, 0, 1)
		local off = pose.shoulder[side]
		local fk1, fk2, fk3 = pose.rot[sh], pose.rot[el], pose.rot[wr]
		if h and w > 0.002 then
			local ut = parts.UpperTorso
			local outward = side == "Right" and 1 or -1
			local pole = h.pole or ut:VectorToWorldSpace(Vector3.new(0.55 * outward, -0.8, 0.35))
			if h.elbowOpen and h.elbowOpen ~= 0 then
				pole += ut:VectorToWorldSpace(Vector3.new(outward, 0, 0)) * (h.elbowOpen * 2)
			end
			local handRot0 = (h.cf * h.grip:Inverse()).Rotation
			local tipPos = h.cf.Position
			local gripPos = h.grip.Position
			local res, t3 = solveRelaxed(ut, rig:info(sh), rig:info(el), rig:info(wr), handRot0,
				function(r) return tipPos - r:VectorToWorldSpace(gripPos) end, pole, 1, rig.lengths.reach * 0.06, off, lim.wrist, 0.65)
			tr[sh] = blend(fk1, res.t1, w)
			tr[el] = blend(fk2, res.t2, w)
			tr[wr] = blend(fk3, t3, w)
			metrics.reach[side] = res.reachError
		else
			tr[sh] = CFrame.new(off) * (fk1 or I)
			tr[el] = fk2 or I
			tr[wr] = fk3 or I
			metrics.reach[side] = 0
		end
	end

	-- bacaklar
	for _, side in SIDES do
		local hip, knee, ank = side .. "Hip", side .. "Knee", side .. "Ankle"
		local f = pose.feet[side]
		if f and f.w > 0.002 then
			local lt = parts.LowerTorso
			local out = side == "Right" and 1 or -1
			local c1p = rig.joints[ank].c1.Position
			local pole = f.pole or lt:VectorToWorldSpace(Vector3.new(0.18 * out, 0, -1))
			local res, t3 = solveRelaxed(lt, rig:info(hip), rig:info(knee), rig:info(ank), f.rot,
				function(r) return f.ankle - r:VectorToWorldSpace(c1p) end, pole, -1, rig.lengths.legUpper * 0.04, nil, lim.ankle)
			local w = math.clamp(f.w, 0, 1)
			tr[hip] = blend(pose.rot[hip], res.t1, w)
			tr[knee] = blend(pose.rot[knee], res.t2, w)
			tr[ank] = blend(pose.rot[ank], t3, w)
			metrics.reach[side .. "Foot"] = res.reachError
		else
			tr[hip] = pose.rot[hip] or I
			tr[knee] = pose.rot[knee] or I
			tr[ank] = pose.rot[ank] or I
			metrics.reach[side .. "Foot"] = 0
		end
	end
end

return Interaction
