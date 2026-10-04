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

-- ── kayıt modu: sessiz çalış, geri sayım + senkron flaşı (video editöründe mp3'ü bu flaşa hizala)
-- workspace attribute BandRecord = true  ->  ekranda 3-2-1 geri sayımı, şarkı zamanı 0'da tek karelik beyaz flaş
local Players = game:GetService("Players")
local gui: ScreenGui? = nil
local label: TextLabel? = nil
local flash: Frame? = nil
local function ensureGui()
	if gui then
		return
	end
	local g = Instance.new("ScreenGui")
	g.Name = "BandRecordOverlay"
	g.IgnoreGuiInset = true
	g.ResetOnSpawn = false
	g.Parent = Players.LocalPlayer:WaitForChild("PlayerGui")
	local l = Instance.new("TextLabel")
	l.Size = UDim2.fromScale(1, 0.3)
	l.Position = UDim2.fromScale(0, 0.35)
	l.BackgroundTransparency = 1
	l.TextScaled = true
	l.Font = Enum.Font.GothamBlack
	l.TextColor3 = Color3.new(1, 1, 1)
	l.TextStrokeTransparency = 0
	l.Text = ""
	l.Parent = g
	local f = Instance.new("Frame")
	f.Size = UDim2.fromScale(1, 1)
	f.BackgroundColor3 = Color3.new(1, 1, 1)
	f.BackgroundTransparency = 1
	f.BorderSizePixel = 0
	f.Parent = g
	gui, label, flash = g, l, f
end
local lastFlashed = false
local function updateRecordOverlay()
	if not workspace:GetAttribute("BandRecord") then
		if gui then
			gui.Enabled = false
		end
		return
	end
	ensureGui()
	;(gui :: ScreenGui).Enabled = true
	local start = workspace:GetAttribute(Config.START_ATTRIBUTE)
	local lbl, fl = label :: TextLabel, flash :: Frame
	if type(start) ~= "number" then
		lbl.Text = ""
		return
	end
	local t = workspace:GetServerTimeNow() - start
	if t < 0 then
		lbl.Text = tostring(math.ceil(-t))
		fl.BackgroundTransparency = 1
		lastFlashed = false
	else
		lbl.Text = ""
		-- şarkı zamanı 0..0.1 sn: beyaz flaş (sonra söner)
		fl.BackgroundTransparency = (t < 0.1) and 0 or 1
	end
end

local debugT = 0
RunService:BindToRenderStep("BandPerformanceUpdate", Enum.RenderPriority.Camera.Value - 1, function(dt)
	syncSound()
	band:update(dt)
	applyCameraMode()
	updateRecordOverlay()
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
