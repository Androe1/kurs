--!strict
--[[
	Müzik saati. Üç kaynaktan şarkı zamanını türetir (öncelik sırasıyla):
	  1) workspace'teki "BandSong" Sound'unun TimePosition'ı (ses ne zaman başlarsa)
	  2) sunucunun yazdığı başlangıç zamanı (workspace:GetServerTimeNow() - start)
	  3) elle ilerletme (testler, çevrimdışı önizleme)

	Sound.TimePosition kaba güncellenir (kare kare sıçrar) -> kendi zamanımızı dt ile ilerletip ölçüme
	yumuşakça yaklaştırırız (drift düzeltme); çok farklıysa (seek/lag) bir anda atlarız.
]]

export type Clock = {
	song: any,
	time: number, -- şarkı zamanı (sn), animasyon için (VISUAL_LEAD dahil)
	rawTime: number,
	bar: number, -- ondalıklı ölçü (0 = ilk ölçü başı)
	beatFloat: number, -- ondalıklı vuruş (ölçü içinde 0..4)
	slotDur: number,
	beatDur: number,
	barDur: number,
	playing: boolean,
	lead: number,
}

local Clock = {}
Clock.__index = Clock

function Clock.new(song: any, lead: number?): Clock
	local beatDur = 60 / song.bpm
	local self = setmetatable({
		song = song,
		time = 0,
		rawTime = 0,
		bar = 0,
		beatFloat = 0,
		beatDur = beatDur,
		barDur = beatDur * song.beatsPerBar,
		slotDur = beatDur * song.beatsPerBar / song.slotsPerBar,
		playing = false,
		lead = lead or 0,
	}, Clock)
	return self :: any
end

function Clock.slotTime(self: Clock, slot: number): number
	return self.song.firstBarTime + slot * self.slotDur
end

function Clock.barTime(self: Clock, bar: number): number
	return self.song.firstBarTime + bar * self.barDur
end

-- measured: ölçülen şarkı zamanı (nil = kaynak yok, kendi saatiyle ilerle). playing: şarkı çalıyor mu
function Clock.update(self: Clock, dt: number, measured: number?, playing: boolean?)
	local isPlaying = playing ~= false and measured ~= nil or playing == true
	self.playing = isPlaying
	if measured ~= nil then
		local err = measured - self.rawTime
		if math.abs(err) > 0.25 or not isPlaying then
			self.rawTime = measured -- seek ya da duraklama: kilitlen
		else
			self.rawTime += dt + err * math.min(1, dt * 8) -- yumuşak drift düzeltme
		end
	elseif isPlaying then
		self.rawTime += dt
	end
	self.time = self.rawTime + self.lead
	local song = self.song
	self.bar = (self.time - song.firstBarTime) / self.barDur
	self.beatFloat = (self.bar % 1) * song.beatsPerBar
end

function Clock.seek(self: Clock, t: number)
	self.rawTime = t
	self.time = t + self.lead
	self.bar = (self.time - self.song.firstBarTime) / self.barDur
	self.beatFloat = (self.bar % 1) * self.song.beatsPerBar
end

return Clock
