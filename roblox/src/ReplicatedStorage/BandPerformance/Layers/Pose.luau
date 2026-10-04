--!strict
--[[
	Karelik poz biriktirici. Her katman buraya KATKI yapar; hiçbiri rig'i doğrudan yazmaz.
	Karıştırma kuralları:
	  - eklem dönüşleri: sırayla çarpılır, her biri ağırlıkla (w) kimlikten kısılır  =>  r = r * identity:Lerp(d, w)
	  - kök ofseti/dönüşü, omuz kayması: ağırlıklı toplama
	  - el/ayak hedefleri: ağırlıklı geçiş (daha sonra gelen katman, w kadar önceki hedefi ezer)
	Böylece "tüm karakteri tek track ile kilitlemek" yerine bağımsız, ağırlıklı katmanlar elde edilir ve
	bir katmanın kapanması (w -> 0) poz atlaması yapmaz.
]]

export type HandTarget = {
	cf: CFrame, -- tutuş çerçevesinin (grip) istenen DÜNYA CFrame'i
	grip: CFrame, -- Hand parçasına göre tutuş çerçevesi (parmak ucu/çubuk tutuşu)
	w: number, -- 0..1 ne kadar IK
	pole: Vector3?, -- dirsek yönü (dünya)
	elbowOpen: number?, -- dirseği dışa aç (stud)
}

export type FootTarget = {
	ankle: Vector3, -- ayak bileği ekleminin DÜNYA konumu
	rot: CFrame, -- ayak parçasının DÜNYA yönelimi (saf dönüş)
	w: number,
	pole: Vector3?,
}

export type Pose = {
	rot: { [string]: CFrame },
	rootOffset: Vector3,
	rootRot: CFrame,
	shoulder: { Left: Vector3, Right: Vector3 }, -- UpperTorso uzayında omuz (klavikula) kayması
	hands: { Left: HandTarget?, Right: HandTarget? },
	feet: { Left: FootTarget?, Right: FootTarget? },
	gaze: Vector3, -- (pitch, yaw, roll) bakış ek açıları (kafa)
}

local Pose = {}
Pose.__index = Pose

function Pose.new(): Pose
	return setmetatable({
		rot = {},
		rootOffset = Vector3.zero,
		rootRot = CFrame.identity,
		shoulder = { Left = Vector3.zero, Right = Vector3.zero },
		hands = {},
		feet = {},
		gaze = Vector3.zero,
	}, Pose) :: any
end

function Pose.addRot(self: Pose, joint: string, delta: CFrame, w: number?)
	local weight = w or 1
	if weight <= 0 then
		return
	end
	local d = weight >= 1 and delta or CFrame.identity:Lerp(delta, weight)
	local cur = self.rot[joint]
	self.rot[joint] = cur and (cur * d) or d
end

--[[
	ANLAMSAL euler (katmanlar bu dili konuşur): x = öne eğilme/öne selam (+ = burun aşağı), y = sola dönüş (+),
	z = sola yatış (+: sağ omuz/kalça yukarı). Roblox'ta +X dönüşü gövdeyi GERİYE yatırır, bu yüzden x işaret değiştirir.
]]
function Pose.angles(v: Vector3): CFrame
	return CFrame.Angles(-v.X, v.Y, v.Z)
end

function Pose.addEuler(self: Pose, joint: string, v: Vector3, w: number?)
	Pose.addRot(self, joint, Pose.angles(v), w)
end

function Pose.addRoot(self: Pose, offset: Vector3, rot: CFrame?, w: number?)
	local weight = w or 1
	self.rootOffset += offset * weight
	if rot then
		self.rootRot = self.rootRot * (weight >= 1 and rot or CFrame.identity:Lerp(rot, weight))
	end
end

function Pose.addShoulder(self: Pose, side: string, offset: Vector3, w: number?)
	local weight = w or 1
	if side == "Left" then
		self.shoulder.Left += offset * weight
	else
		self.shoulder.Right += offset * weight
	end
end

function Pose.setHand(self: Pose, side: string, tgt: HandTarget)
	local hands: any = self.hands
	local prev = hands[side] :: HandTarget?
	if prev and tgt.w < 1 then
		local w = tgt.w
		local merged: HandTarget = {
			cf = prev.cf:Lerp(tgt.cf, w),
			grip = prev.grip:Lerp(tgt.grip, w),
			w = prev.w + (1 - prev.w) * w,
			pole = tgt.pole or prev.pole,
			elbowOpen = (prev.elbowOpen or 0) + ((tgt.elbowOpen or 0) - (prev.elbowOpen or 0)) * w,
		}
		hands[side] = merged
	else
		hands[side] = tgt
	end
end

function Pose.setFoot(self: Pose, side: string, tgt: FootTarget)
	local feet: any = self.feet
	local prev = feet[side] :: FootTarget?
	if prev and tgt.w < 1 then
		local w = tgt.w
		feet[side] = {
			ankle = prev.ankle:Lerp(tgt.ankle, w),
			rot = prev.rot:Lerp(tgt.rot, w),
			w = prev.w + (1 - prev.w) * w,
			pole = tgt.pole or prev.pole,
		}
	else
		feet[side] = tgt
	end
end

return Pose
