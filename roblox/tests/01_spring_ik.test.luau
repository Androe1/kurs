local Rbx = R.Rbx
local T = R.T
local Spring = require(R.Root.Util.Spring)
local IK = require(R.Root.Rig.TwoBoneIK)
local R15Rig = require(R.Root.Rig.R15Rig)

T.section("Spring: kapalı form, dt'den bağımsız, overshoot")
do
	local function run(dt, freq, zeta, n)
		local s = Spring.Spring.new(0, freq, zeta)
		local peak = 0
		for i = 1, n do
			local x = s:step(1, dt)
			peak = math.max(peak, x)
		end
		return s.x, peak
	end
	local xA = run(1 / 60, 4, 0.5, 120) -- 2 sn
	local xB = run(1 / 30, 4, 0.5, 60)
	local xC = run(1 / 240, 4, 0.5, 480)
	T.near(xA, xB, 1e-6, "30/60 fps aynı sonuç")
	T.near(xA, xC, 1e-6, "240/60 fps aynı sonuç")
	local _, peak = run(1 / 60, 4, 0.5, 120)
	T.check(peak > 1.1 and peak < 1.25, "ζ=0.5 -> ~%16 overshoot, bulunan " .. peak)
	local _, peakCrit = run(1 / 60, 4, 1.0, 240)
	T.check(peakCrit <= 1.0001, "kritik sönümde overshoot yok")
	local _, peakOver = run(1 / 60, 4, 2.0, 240)
	T.check(peakOver <= 1.0001, "aşırı sönümde overshoot yok")
	-- hız sürekliliği: yay hedefi değişince hız sıçramaz
	local s = Spring.Spring.new(0, 5, 0.7)
	local vPrev, maxJump = 0, 0
	for i = 1, 200 do
		s:step(i < 100 and 1 or -1, 1 / 60)
		maxJump = math.max(maxJump, math.abs(s.v - vPrev))
		vPrev = s.v
	end
	T.check(maxJump < 40, "hedef değişince yay ivmeli ama sürekli (max Δv " .. string.format("%.1f", maxJump) .. " = ω²·Δx·dt mertebesi, ani sıçrama yok)")
end

T.section("R15Rig: bağlama, FK dinlenme pozu")
local model = R.mockR15()
local rig = R15Rig.new(model)
T.near(rig.lengths.armUpper, 1.2, 1e-6, "üst kol uzunluğu")
T.near(rig.lengths.armLower, 1.0, 1e-6, "ön kol uzunluğu")
T.near(rig.lengths.legUpper, 1.2, 1e-6, "üst bacak")
local parts = rig:forward({})
for n, p in pairs(model:GetChildren()) do end
for _, part in ipairs(model:GetChildren()) do
	T.check((parts[part.Name].Position - part.CFrame.Position).Magnitude < 1e-6, "FK dinlenme = model: " .. part.Name)
end

T.section("TwoBoneIK: kollar hedefe ulaşıyor, dirsek anatomik")
local function solveArm(side, wristWorld, handOrient)
	local sh, el, wr = side .. "Shoulder", side .. "Elbow", side .. "Wrist"
	local ut = parts.UpperTorso
	local endCF = CFrame.new(wristWorld) * (handOrient or CFrame.identity) * rig.joints[wr].c1:Inverse() -- el: bilek eklemi tam wristWorld'de
	-- c1 offseti dönüşsüz olduğundan: Hand merkezi = wrist - R*c1.Position... endCF * c1 pos = wristWorld
	local pole = Vector3.new(side == "Right" and 0.5 or -0.5, -0.8, 0.4)
	return IK.solveChain(ut, rig:info(sh), rig:info(el), rig:info(wr), endCF, pole, 1)
end
for _, case in ipairs({
	{ "Right", Vector3.new(1.0, 0.5, -1.4) },
	{ "Left", Vector3.new(-1.2, 0.2, -1.6) },
	{ "Right", Vector3.new(0.2, 1.2, -1.0) },
	{ "Left", Vector3.new(-1.5, -0.4, -0.2) }, -- yan/aşağı
}) do
	local res = solveArm(case[1], case[2])
	T.check(res.reachError < 1e-3, case[1] .. " hedefe ulaşır, hata " .. res.reachError)
	-- yeni Transform'larla FK: bilek eklemi hedefte mi?
	local tr = { [case[1] .. "Shoulder"] = res.t1, [case[1] .. "Elbow"] = res.t2, [case[1] .. "Wrist"] = res.t3 }
	local p2 = rig:forward(tr)
	local wristJoint = p2[case[1] .. "LowerArm"] * rig.joints[case[1] .. "Wrist"].c0
	T.check((wristJoint.Position - case[2]).Magnitude < 1e-3, case[1] .. " FK ile doğrulanan bilek konumu")
	-- dirsek: pozitif fleksiyon ve makul açı
	local axis, ang = res.t2:ToAxisAngle()
	local localX = axis:Dot(Vector3.new(1, 0, 0))
	T.check(ang < 0.01 or (localX > 0.95 and ang < math.rad(160)), string.format("dirsek menteşe ekseni yerel +X (dot %.3f, açı %.0f°)", localX, math.deg(ang)))
end
-- hedefe erişilemezse: kol uzar ama hedefi geçmez, patlamaz
do
	local res = solveArm("Right", Vector3.new(4, 0.5, -3))
	T.check(res.reachError > 0.5 and res.reachError < 5, "erişilemeyen hedefte yumuşak uzama, hata " .. string.format("%.2f", res.reachError))
	T.check(res.t1.p.Magnitude < 1e-6, "Transform yalnızca dönüş")
end

T.section("Bacak: diz öne, ayak yere basık")
do
	local ut = parts.LowerTorso
	local footTarget = Vector3.new(0.5, -2.6, 0) + Vector3.new(0, 0.5, 0) -- ayak bileği 0.5 yukarı: diz bükülmeli
	local endCF = CFrame.new(footTarget) * rig.joints.RightAnkle.c1:Inverse()
	local res = IK.solveChain(ut, rig:info("RightHip"), rig:info("RightKnee"), rig:info("RightAnkle"), endCF, Vector3.new(0, 0, -1), -1)
	T.check(res.reachError < 1e-3, "bacak hedefe ulaşır")
	local tr = { RightHip = res.t1, RightKnee = res.t2, RightAnkle = res.t3 }
	local p2 = rig:forward(tr)
	local kneeJoint = p2.RightUpperLeg * rig.joints.RightKnee.c0
	T.check(kneeJoint.Position.Z < -0.05, "diz ileri doğru (-Z) çıkıyor: z=" .. string.format("%.2f", kneeJoint.Position.Z))
	local axis, ang = res.t2:ToAxisAngle()
	T.check(axis:Dot(Vector3.new(-1, 0, 0)) > 0.95, "diz -X ekseninde büküldü")
end

T.section("Spring.impulseForPeak: ilk tepe tam istenen genlik")
for _, cfg in ipairs({ { 3.4, 0.42 }, { 5, 0.7 }, { 4, 1.0 }, { 4, 1.6 }, { 6, 0.3 } }) do
	local s = Spring.Spring.new(0, cfg[1], cfg[2])
	s:impulseForPeak(0.1)
	local peak = 0
	for i = 1, 300 do peak = math.max(peak, s:step(0, 1 / 240)) end
	T.near(peak, 0.1, 0.004, string.format("tepe genliği f=%.1f ζ=%.2f", cfg[1], cfg[2]))
end

T.section("IK: omuz kayması (klavikula)")
do
	local ut = parts.UpperTorso
	local off = Vector3.new(0, 0.12, -0.05)
	local target = Vector3.new(1.0, 0.5, -1.4)
	local endCF = CFrame.new(target) * rig.joints.RightWrist.c1:Inverse()
	local res = IK.solveChain(ut, rig:info("RightShoulder"), rig:info("RightElbow"), rig:info("RightWrist"), endCF, Vector3.new(0.5, -0.8, 0.4), 1, 0, off)
	T.check(res.reachError < 1e-3, "kaymış omuzla da hedefe ulaşır")
	local p2 = rig:forward({ RightShoulder = res.t1, RightElbow = res.t2, RightWrist = res.t3 })
	local w = p2.RightLowerArm * rig.joints.RightWrist.c0
	T.check((w.Position - target).Magnitude < 1e-3, "FK ile bilek konumu doğrulandı")
	local shoulderWorld = p2.RightUpperArm * rig.joints.RightShoulder.c1
	local expected = ut * rig.joints.RightShoulder.c0 * off
	T.check((shoulderWorld.Position - expected).Magnitude < 1e-3, "omuz ekleminin kayması uygulanıyor")
end
