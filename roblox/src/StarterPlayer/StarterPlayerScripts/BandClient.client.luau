--!strict
--[[
	İSTEMCİ: animasyonun asıl üretildiği yer (Motor6D.Transform + prop CFrame'leri yalnızca yerelde yazılır).
	  - saat: sunucunun yazdığı başlangıç zamanı (herkes aynı karede)
	  - ses: yerel Sound, sunucu saatine göre başlatılır ve kayma >0.12 sn ise düzeltilir (animasyon sese değil SAATE kilitli;
	    ses saate yaklaştırılır) -> ses gecikmesi için Config.VISUAL_LEAD
	  - güncelleme RenderStep'te, kameradan ÖNCE: Roblox'un animasyon güncellemesinden sonra yazdığımız için Animator ezmez
	Kamera: workspace attribute "BandCamera" = "auto" | "front" | "guitarSide" | ... (boşsa kamera kullanıcıda kalır)
	Hata ayıklama: workspace attribute "BandDebug" = true -> 5 sn'de bir temas hatası/duruş özeti
]]

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local SoundService = game:GetService("SoundService")

local BandPerformance = require(ReplicatedStorage:WaitForChild("BandPerformance"))
local Config = BandPerformance.Config
local Song = require(ReplicatedStorage.BandPerformance.Data.SongMap)

local container: Instance = workspace:FindFirstChild("Band") or workspace
local band = BandPerformance.new({
	container = container,
	timeSource = BandPerformance.serverTimeSource(workspace),
	buildProps = true,
	propsParent = workspace,
	getCameraPosition = function()
		local cam = workspace.CurrentCamera
		return cam and cam.CFrame.Position or nil
	end,
})

-- ── ses
local sound: Sound? = (workspace:FindFirstChild(Config.SOUND_NAME) or SoundService:FindFirstChild(Config.SOUND_NAME)) :: any
if sound == nil then
	local id = workspace:GetAttribute("BandSongId")
	if type(id) == "string" and id ~= "" then
		local s = Instance.new("Sound")
		s.Name = Config.SOUND_NAME
		s.SoundId = id
		s.Looped = false
		s.Parent = SoundService
		sound = s
	end
end

local function syncSound()
	if sound == nil then
		return
	end
	local start = workspace:GetAttribute(Config.START_ATTRIBUTE)
	if type(start) ~= "number" then
		if sound.IsPlaying then
			sound:Stop()
		end
		return
	end
	local t = workspace:GetServerTimeNow() - start
	if t < 0 or t > Song.duration then
		if sound.IsPlaying and t > Song.duration then
			sound:Stop()
		end
		return
	end
	if not sound.IsPlaying then
		sound.TimePosition = t
		sound:Play()
	elseif math.abs(sound.TimePosition - t) > 0.12 then
		sound.TimePosition = t
	end
end

-- ── kamera
local cameraRig = BandPerformance.CameraRig.new()
local cameraMode: string? = nil
local function applyCameraMode()
	local mode = workspace:GetAttribute("BandCamera")
	if type(mode) == "string" and mode ~= "" then
		if mode ~= cameraMode then
			cameraMode = mode
			workspace.CurrentCamera.CameraType = Enum.CameraType.Scriptable
			if mode ~= "auto" then
				cameraRig:cut(mode, band)
			end
		end
	elseif cameraMode ~= nil then
		cameraMode = nil
		workspace.CurrentCamera.CameraType = Enum.CameraType.Custom
	end
end

local debugT = 0
RunService:BindToRenderStep("BandPerformanceUpdate", Enum.RenderPriority.Camera.Value - 1, function(dt)
	syncSound()
	band:update(dt)
	applyCameraMode()
	if cameraMode ~= nil then
		if cameraMode == "auto" then
			cameraRig:direct(band)
		end
		workspace.CurrentCamera.CFrame = cameraRig:update(dt, band)
	end
	if workspace:GetAttribute("BandDebug") then
		debugT += dt
		if debugT > 5 then
			debugT = 0
			for role, m in band:getMetrics() do
				print(string.format("[Band] %-6s %-10s elHata L%.3f R%.3f", role, m.state, m.handError.Left, m.handError.Right))
			end
		end
	end
end)
