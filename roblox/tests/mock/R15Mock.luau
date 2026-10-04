--!nonstrict
--[[ Varsayılan R15 ölçülerine yakın, sahte (Instance'sız) bir R15 modeli. Dinlenme pozu: kollar aşağı, tüm
     eklem çerçeveleri parçalarla hizalı. Karakter -Z'ye bakar, sağ taraf +X. HRP orijinde (test için). ]]
local Rbx = ...
local V = Vector3.new

local function build(opts)
	opts = opts or {}
	local s = opts.scale or 1
	local model = Rbx.newInstance("Model", opts.name or "MockR15")
	local function part(name, center)
		local p = Rbx.newInstance("Part", name, { CFrame = CFrame.new(center * s), Anchored = false })
		Rbx.parent(p, model)
		return p
	end
	local centers = {
		HumanoidRootPart = V(0, 0, 0), LowerTorso = V(0, 0, 0), UpperTorso = V(0, 1.0, 0), Head = V(0, 2.3, 0),
		RightUpperArm = V(1.5, 1.0, 0), RightLowerArm = V(1.5, -0.1, 0), RightHand = V(1.5, -0.8, 0),
		LeftUpperArm = V(-1.5, 1.0, 0), LeftLowerArm = V(-1.5, -0.1, 0), LeftHand = V(-1.5, -0.8, 0),
		RightUpperLeg = V(0.5, -0.8, 0), RightLowerLeg = V(0.5, -2.0, 0), RightFoot = V(0.5, -2.8, 0),
		LeftUpperLeg = V(-0.5, -0.8, 0), LeftLowerLeg = V(-0.5, -2.0, 0), LeftFoot = V(-0.5, -2.8, 0),
	}
	local parts = {}
	for n, c in pairs(centers) do parts[n] = part(n, c) end
	-- eklem dünya konumları (dinlenme) -> C0/C1 dönüşüz ofset
	local joints = {
		{ "Root", "HumanoidRootPart", "LowerTorso", V(0, 0, 0) },
		{ "Waist", "LowerTorso", "UpperTorso", V(0, 0.2, 0) },
		{ "Neck", "UpperTorso", "Head", V(0, 1.8, 0) },
		{ "RightShoulder", "UpperTorso", "RightUpperArm", V(1.5, 1.6, 0) },
		{ "RightElbow", "RightUpperArm", "RightLowerArm", V(1.5, 0.4, 0) },
		{ "RightWrist", "RightLowerArm", "RightHand", V(1.5, -0.6, 0) },
		{ "LeftShoulder", "UpperTorso", "LeftUpperArm", V(-1.5, 1.6, 0) },
		{ "LeftElbow", "LeftUpperArm", "LeftLowerArm", V(-1.5, 0.4, 0) },
		{ "LeftWrist", "LeftLowerArm", "LeftHand", V(-1.5, -0.6, 0) },
		{ "RightHip", "LowerTorso", "RightUpperLeg", V(0.5, -0.2, 0) },
		{ "RightKnee", "RightUpperLeg", "RightLowerLeg", V(0.5, -1.4, 0) },
		{ "RightAnkle", "RightLowerLeg", "RightFoot", V(0.5, -2.6, 0) },
		{ "LeftHip", "LowerTorso", "LeftUpperLeg", V(-0.5, -0.2, 0) },
		{ "LeftKnee", "LeftUpperLeg", "LeftLowerLeg", V(-0.5, -1.4, 0) },
		{ "LeftAnkle", "LeftLowerLeg", "LeftFoot", V(-0.5, -2.6, 0) },
	}
	for _, j in ipairs(joints) do
		local p0, p1 = parts[j[2]], parts[j[3]]
		local wp = j[4] * s
		local m = Rbx.newInstance("Motor6D", j[1], {
			Part0 = p0, Part1 = p1,
			C0 = CFrame.new(wp - p0.CFrame.Position),
			C1 = CFrame.new(wp - p1.CFrame.Position),
			Transform = CFrame.identity,
		})
		Rbx.parent(m, p1)
	end
	model.PrimaryPart = parts.HumanoidRootPart
	return model
end
return build
