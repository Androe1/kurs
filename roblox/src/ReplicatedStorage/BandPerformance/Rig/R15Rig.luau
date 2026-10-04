--!strict
--[[
	R15 rig bağlama + kendi ileri kinematiği (FK).

	Var olan Motor6D'leri DEĞİŞTİRMEZ: yalnızca Transform'u yazar (C0/C1 olduğu gibi kalır).
	Bunun anlamı: modele dokunmadan animasyon verirsin; sistemi kapatınca rig eski haline döner.
	FK'yi Roblox'a bırakmayıp kendimiz hesaplıyoruz çünkü IK ve enstrüman hedefleri aynı karede
	kemiklerin dünya konumuna ihtiyaç duyuyor (Roblox'un fizik/animasyon güncellemesini beklemeden).

	Eklem sırası (üst -> alt): Root, Waist, Neck, {R,L}Shoulder/Elbow/Wrist, {R,L}Hip/Knee/Ankle.
]]

local Root = script:FindFirstAncestor("BandPerformance")
local IK = require(Root.Rig.TwoBoneIK)

export type Joint = {
	name: string,
	motor: any, -- Motor6D
	part0: string,
	part1: string,
	c0: CFrame,
	c1: CFrame,
	bone: Vector3, -- eklem uzayında, çocuk eklemine vektör (yoksa sıfır)
}

export type Rig = {
	model: Model,
	joints: { [string]: Joint },
	order: { string },
	rootCF: CFrame,
	lengths: { armUpper: number, armLower: number, legUpper: number, legLower: number, reach: number },
	partCF: { [string]: CFrame },
}

local R15Rig = {}
R15Rig.__index = R15Rig

-- {eklem, Part0, Part1, çocuk eklem (kemik yönü için)}
local DEF = {
	{ "Root", "HumanoidRootPart", "LowerTorso", "Waist" },
	{ "Waist", "LowerTorso", "UpperTorso", "Neck" },
	{ "Neck", "UpperTorso", "Head", nil },
	{ "RightShoulder", "UpperTorso", "RightUpperArm", "RightElbow" },
	{ "RightElbow", "RightUpperArm", "RightLowerArm", "RightWrist" },
	{ "RightWrist", "RightLowerArm", "RightHand", nil },
	{ "LeftShoulder", "UpperTorso", "LeftUpperArm", "LeftElbow" },
	{ "LeftElbow", "LeftUpperArm", "LeftLowerArm", "LeftWrist" },
	{ "LeftWrist", "LeftLowerArm", "LeftHand", nil },
	{ "RightHip", "LowerTorso", "RightUpperLeg", "RightKnee" },
	{ "RightKnee", "RightUpperLeg", "RightLowerLeg", "RightAnkle" },
	{ "RightAnkle", "RightLowerLeg", "RightFoot", nil },
	{ "LeftHip", "LowerTorso", "LeftUpperLeg", "LeftKnee" },
	{ "LeftKnee", "LeftUpperLeg", "LeftLowerLeg", "LeftAnkle" },
	{ "LeftAnkle", "LeftLowerLeg", "LeftFoot", nil },
}

R15Rig.JOINT_ORDER = {}
for _, d in DEF do
	table.insert(R15Rig.JOINT_ORDER, d[1])
end

local function findMotor(model: Model, name: string): any
	local m = model:FindFirstChild(name, true)
	if m == nil then
		error(("R15Rig: '%s' Motor6D'si bulunamadı (%s). R15 rig gerekli."):format(name, model.Name))
	end
	return m
end

function R15Rig.new(model: Model): Rig
	local joints: { [string]: Joint } = {}
	local order = {}
	local motors: { [string]: any } = {}
	for _, d in DEF do
		motors[d[1]] = findMotor(model, d[1])
	end
	for _, d in DEF do
		local m = motors[d[1]]
		local childName = d[4]
		local bone = Vector3.new(0, 0, 0)
		if childName then
			bone = m.C1:Inverse() * motors[childName].C0.Position
		end
		joints[d[1]] = {
			name = d[1], motor = m, part0 = d[2], part1 = d[3],
			c0 = m.C0, c1 = m.C1, bone = bone,
		}
		table.insert(order, d[1])
	end
	local hrp = model:FindFirstChild("HumanoidRootPart", true)
	local self = setmetatable({
		model = model,
		joints = joints,
		order = order,
		rootCF = hrp and hrp.CFrame or CFrame.identity,
		partCF = {},
		lengths = {
			armUpper = joints.RightShoulder.bone.Magnitude,
			armLower = joints.RightElbow.bone.Magnitude,
			legUpper = joints.RightHip.bone.Magnitude,
			legLower = joints.RightKnee.bone.Magnitude,
			reach = joints.RightShoulder.bone.Magnitude + joints.RightElbow.bone.Magnitude,
		},
	}, R15Rig)
	return self :: any
end

function R15Rig.setRootCF(self: Rig, cf: CFrame)
	self.rootCF = cf
end

-- Transform tablosundan tüm parçaların dünya CFrame'ini hesapla (eksik eklem = kimlik)
function R15Rig.forward(self: Rig, transforms: { [string]: CFrame }): { [string]: CFrame }
	local cf = self.partCF
	cf.HumanoidRootPart = self.rootCF
	for _, name in self.order do
		local j = self.joints[name]
		local t = transforms[name] or CFrame.identity
		cf[j.part1] = cf[j.part0] * j.c0 * t * j.c1:Inverse()
	end
	return cf
end

-- Eklemin çözümlemesi için bilgi (IK girişi)
function R15Rig.info(self: Rig, name: string): IK.JointInfo
	local j = self.joints[name]
	return { c0 = j.c0, c1 = j.c1, bone = j.bone }
end

-- Eklem çerçevesi (Part0 tarafı, Transform uygulanmadan): omuz/kalça pivotu
function R15Rig.jointFrame(self: Rig, parts: { [string]: CFrame }, name: string): CFrame
	local j = self.joints[name]
	return parts[j.part0] * j.c0
end

function R15Rig.apply(self: Rig, transforms: { [string]: CFrame })
	for _, name in self.order do
		self.joints[name].motor.Transform = transforms[name] or CFrame.identity
	end
end

function R15Rig.reset(self: Rig)
	for _, name in self.order do
		self.joints[name].motor.Transform = CFrame.identity
	end
end

return R15Rig
