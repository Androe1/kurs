--!strict
--[[
	Tüm ayarlar burada. Hareketin "karakteri" (ağır/hafif, ne kadar sallanır, ne kadar abartılır)
	rol profillerinde; sahne yerleşimi Stage'de. Birim: stud, saniye, radyan (açılar derece yazılıp çevrilir).
	Etiketler (tag) ve model adları: workspace'te "BandRole" attribute'u (Guitar/Bass/Drums/Vocal) olan
	R15 modelleri otomatik bulunur; yoksa Models adlarına bakılır.
]]

local Config = {}

Config.TAG = "BandMember"
Config.ROLE_ATTRIBUTE = "BandRole"
-- model adı -> rol (BandRole attribute'u yoksa)
Config.MODEL_NAMES = {
	Gitarist = "Guitar", Gitarsit = "Guitar", Guitarist = "Guitar",
	Basgitar = "Bass", Basist = "Bass", Basci = "Bass", Bassist = "Bass",
	Baterist = "Drums", Batersit = "Drums", Drummer = "Drums",
	Vokalist = "Vocal", Vocalist = "Vocal",
}

-- şarkı başlangıç zamanı (sunucu saati) workspace attribute'u: Band sunucusu yazar, istemciler okur
Config.START_ATTRIBUTE = "BandStartServerTime"
Config.SOUND_NAME = "BandSong" -- workspace'te bu adda bir Sound varsa saat ona kilitlenir

-- Müzikal zaman: görsel vuruş ses vuruşunun ne kadar önünde (sn). + = animasyon erken. Ses gecikmesini telafi eder.
Config.VISUAL_LEAD = 0.02

local function deg(d: number): number
	return math.rad(d)
end
Config.deg = deg

--[[ Rol profilleri. Çarpanlar enerji (0..1) ile ölçeklenir.
	bounce   : vuruşta kalça çökmesi (stud)       sway : yavaş ağırlık aktarımı genliği (stud)
	nod      : vuruşta kafa yatışı (rad)          lean : ileri/geri eğilme (rad)
	chestCounter: göğüs karşı dönüşü oranı        head* : kafanın torsoyu "önceden" yönlendirmesi
	weightPeriodBars: ağırlık transferi periyodu  stance: ayak aralığı/açısı
]]
Config.profiles = {
	Guitar = {
		bounce = 0.075, bounceDelay = 0.0, sway = 0.15, nod = deg(7), lean = deg(5), chestCounter = 0.6,
		headLead = 0.35, weightPeriodBars = 2, footTap = 0.6, strapDrop = 0.0,
		stanceYaw = deg(24), stanceWidth = 1.15,
		-- karakterin sahnedeki "performans yönü" (yaw, derece): davulcuya/kameraya hafif dönük
		facing = deg(-18),
	},
	Bass = {
		-- bas: daha ağır, daha az ama güçlü hareket; kalça/gövde groove'u, sustain'de sakin
		bounce = 0.05, bounceDelay = 0.012, sway = 0.12, nod = deg(5), lean = deg(3), chestCounter = 0.8,
		headLead = 0.2, weightPeriodBars = 4, footTap = 0.35, strapDrop = 0.0,
		stanceYaw = deg(18), stanceWidth = 1.3,
		facing = deg(22),
	},
	Drums = {
		bounce = 0.0, bounceDelay = 0.0, sway = 0.0, nod = deg(8), lean = deg(7), chestCounter = 0.5,
		headLead = 0.3, weightPeriodBars = 4, footTap = 0.0, strapDrop = 0.0,
		stanceYaw = 0, stanceWidth = 1.0, facing = 0,
	},
	Vocal = {
		bounce = 0.06, bounceDelay = 0.0, sway = 0.2, nod = deg(8), lean = deg(7), chestCounter = 0.7,
		headLead = 0.5, weightPeriodBars = 2, footTap = 0.4, strapDrop = 0.0,
		stanceYaw = deg(14), stanceWidth = 1.2, facing = deg(0),
	},
}

-- Yay parametreleri (freq Hz, damping ζ). Sert gövde -> gevşek uç: lead & follow kendiliğinden doğar.
Config.springs = {
	pelvisY = { 3.4, 0.42 },
	pelvisShift = { 2.2, 0.8 },
	pelvisRot = { 3.0, 0.7 },
	waist = { 3.8, 0.6 },
	neck = { 4.6, 0.5 },
	shoulder = { 5.5, 0.55 },
	hand = { 6.0, 0.5 },
	elbow = { 4.5, 0.6 },
	instrument = { 4.0, 0.45 },
	ikWeight = { 1.4, 1.0 },
}

-- Eklem hareket sınırları (güvenlik; anatomik saçmalık olmasın)
Config.limits = {
	waistPitch = deg(35), waistYaw = deg(32), waistRoll = deg(20),
	neckPitch = deg(40), neckYaw = deg(55), neckRoll = deg(22),
	wrist = deg(80), ankle = deg(50), rootRoll = deg(12), rootYaw = deg(30),
	elbowFlexMax = deg(150), kneeFlexMax = deg(145),
}

-- Kamera yardımcı ön ayarları (CameraRig): torso/instrument'a göre
Config.cameraShots = {
	"front", "threeQuarterFront", "side", "threeQuarterBack",
	"handsCloseUp", "guitarSide", "bassSide", "drummerSide", "lowAngle", "elevated",
}

return Config
