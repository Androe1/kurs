--!strict
--[[
	Rig hazırlığı (idempotent): karakteri prosedürel animasyona hazır hale getirir. Modelin geometrisini/Motor6D'lerini
	DEĞİŞTİRMEZ; yalnızca animasyonu bozacak şeyleri kapatır:
	  - HumanoidRootPart anchored, diğer parçalar unanchored (Motor6D zinciri kökten taşınır; hepsi anchored olursa
	    Transform görsel olarak uygulanmaz)
	  - varsayılan "Animate" scripti ve çalan AnimationTrack'ler durur (Motor6D.Transform'u ezmesinler)
	  - Humanoid durum makinesi kapalı (düşme/yürüme animasyonu çıkmasın)
]]

local RigPrep = {}

function RigPrep.prepare(model: Model)
	local hrp = model:FindFirstChild("HumanoidRootPart", true) :: any
	if hrp then
		hrp.Anchored = true
	end
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") and d ~= hrp then
			local bp: any = d
			bp.Anchored = false
			bp.CanCollide = false
		elseif d:IsA("LocalScript") or d:IsA("Script") then
			if d.Name == "Animate" then
				local sc: any = d
				sc.Disabled = true
			end
		end
	end
	local hum = model:FindFirstChildOfClass("Humanoid") :: any
	if hum then
		hum.WalkSpeed = 0
		hum.JumpPower = 0
		hum.AutoRotate = false
		hum.EvaluateStateMachine = false
		hum.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
		local animator = hum:FindFirstChildOfClass("Animator") :: any
		if animator then
			for _, track in animator:GetPlayingAnimationTracks() do
				track:Stop(0)
			end
		end
	end
end

return RigPrep
