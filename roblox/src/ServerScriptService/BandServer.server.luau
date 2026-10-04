--!strict
--[[
	SUNUCU: yalnızca "ne zaman ve hangi karakterler" sorumluluğu.
	  - R15 karakterleri bulur ve animasyona hazırlar (HRP anchored, Animate kapalı) - idempotent
	  - ortak şarkı başlangıç zamanını (sunucu saati) workspace attribute'una yazar; şarkı bitince (isteğe bağlı) tekrar başlatır
	Sunucu Motor6D yazmaz: Transform replike olmaz, her istemci animasyonu aynı saatten KENDİ üretir (BandClient).
	Bu yüzden ağ trafiği yok, gecikme yok, herkes aynı karede aynı vuruşu görür.

	Ayarlar (workspace attribute): BandLoop (bool, varsayılan true), BandLeadIn (sn, varsayılan 3; BandRecord açıkken 6),
	BandSongId (rbxassetid://...), BandRecord (bool: sessiz kayıt modu, geri sayım + flaş, döngü kapalı)
]]

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local BandPerformance = require(ReplicatedStorage:WaitForChild("BandPerformance"))
local RigPrep = require(ReplicatedStorage.BandPerformance.Rig.RigPrep)
local Config = BandPerformance.Config
local Song = require(ReplicatedStorage.BandPerformance.Data.SongMap)

local container: Instance = workspace:FindFirstChild("Band") or workspace

for _, e in BandPerformance.discover(container) do
	RigPrep.prepare(e.model)
end

if workspace:GetAttribute("BandLoop") == nil then
	workspace:SetAttribute("BandLoop", true)
end
local recording = workspace:GetAttribute("BandRecord") == true
if recording then
	workspace:SetAttribute("BandLoop", false)
end
local leadIn = workspace:GetAttribute("BandLeadIn")
if type(leadIn) ~= "number" then
	leadIn = recording and 6 or 3
end

local function schedule()
	workspace:SetAttribute(Config.START_ATTRIBUTE, workspace:GetServerTimeNow() + (leadIn :: number))
end

schedule()
task.spawn(function()
	while true do
		task.wait(1)
		local start = workspace:GetAttribute(Config.START_ATTRIBUTE)
		if type(start) == "number" and workspace:GetServerTimeNow() - start > Song.duration + 1.5 then
			if workspace:GetAttribute("BandLoop") then
				schedule()
			else
				workspace:SetAttribute(Config.START_ATTRIBUTE, nil)
			end
		end
	end
end)
