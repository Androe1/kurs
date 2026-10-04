--!strict
--[[
	SongMap (analyze_song.py çıktısı) -> performans "notası".

	SongMap ölçülen şeydir: tempo ızgarası, 16'lık başına davul/gitar bandı enerjisi, yarım ölçü başına akor kökü,
	vuruş başına bas notası. Burada bu ölçümler çalınabilir OLAYLARA çevrilir:
	  drums  : kick / snare / hat / hatOpen / crash / ride / tom (şiddetli, kol atamalı)
	  guitar : strum ızgarası (down/up/ghost/mute/accent) + akor değişimleri (perde = fret)
	  bass   : pluck olayları (tel/perde/parmak/süre) - boşluklar korunur
	Ölçüm gürültülüyse (distorsiyonlu miks) davul için ölçümü stil önceliğiyle (prior) birleştiririz; ağırlıklı
	olarak ölçüm kazanır. Bu bir transkripsiyon değil: tutarlı, müzikle ilişkili bir performans iskeleti.
]]

local Root = script:FindFirstAncestor("BandPerformance")
local Rng = require(Root.Util.Rng)
local DrumKit = require(Root.Performers.DrumKit)

export type Section = {
	index: number, startBar: number, endBar: number, startT: number, endT: number,
	kind: string, intensity: number,
}

export type DrumEvent = { t: number, slot: number, kind: string, str: number, drum: string, hand: string?, fill: boolean?, dropped: boolean?, hit: any? }
export type StrumEvent = { t: number, slot: number, dir: number, str: number, kind: string }
export type ChordEvent = { t: number, bar: number, pc: number, quality: string, fret: number, string: number }
export type BassEvent = { t: number, slot: number, midi: number, str: number, string: number, fret: number, dur: number, finger: number }
export type BarStyle = {
	bar: number, cycle: number, phase: number, accentBoost: number, headAmp: number,
	stanceShift: boolean, fill: boolean, hold: boolean, swayDir: number, vocalOn: boolean,
	swayMul: number, bounceMul: number, leanMul: number,
}

export type Score = {
	song: any, seed: number,
	slotDur: number, barDur: number, beatDur: number,
	sections: { Section },
	drums: { DrumEvent }, guitar: { StrumEvent }, chords: { ChordEvent }, bass: { BassEvent },
	barStyles: { BarStyle },
}

local Score = {}

local function lane(str: string, slot: number): number
	local c = string.sub(str, slot + 1, slot + 1)
	if c == "." or c == "" then
		return 0
	end
	return (tonumber(c) or 0) / 9
end

-- ───── bölümler ─────
local function buildSections(song: any, slotDur: number, barDur: number): { Section }
	local starts = song.sectionStarts
	local out: { Section } = {}
	local energy = song.energy
	local means = {}
	local lo, hi = 1e9, -1e9
	for i, s in starts do
		local e = (starts[i + 1] or song.bars) - 1
		local sum = 0
		for b = s, e do
			sum += energy[b + 1] or 0
		end
		local mean = sum / math.max(1, e - s + 1)
		means[i] = mean
		lo, hi = math.min(lo, mean), math.max(hi, mean)
	end
	for i, s in starts do
		local e = starts[i + 1] or song.bars
		local m = means[i]
		local norm = (m - lo) / math.max(hi - lo, 1e-6)
		local kind = "verse"
		if i == 1 then
			kind = "intro"
		elseif i == #starts then
			kind = "outro"
		elseif norm > 0.62 then
			kind = "chorus"
		elseif norm < 0.3 then
			kind = "calm"
		end
		table.insert(out, {
			index = i, startBar = s, endBar = e,
			startT = song.firstBarTime + s * barDur, endT = song.firstBarTime + e * barDur,
			kind = kind, intensity = 0.3 + 0.7 * norm,
		})
	end
	return out
end

function Score.sectionAtBar(self: Score, bar: number): Section
	for _, s in self.sections do
		if bar >= s.startBar and bar < s.endBar then
			return s
		end
	end
	return self.sections[#self.sections]
end

-- ───── davul ─────
local PRIOR = {
	intro = { k = { [0] = 1 }, s = {}, h = { [0] = 0.6, [4] = 0.6, [8] = 0.6, [12] = 0.6 } },
	calm = { k = { [0] = 1, [10] = 0.6 }, s = { [4] = 0.8, [12] = 0.8 }, h = { [0] = 0.5, [4] = 0.5, [8] = 0.5, [12] = 0.5 } },
	verse = { k = { [0] = 1, [10] = 0.7 }, s = { [4] = 1, [12] = 1 }, h = { [0] = 0.6, [2] = 0.5, [4] = 0.6, [6] = 0.5, [8] = 0.6, [10] = 0.5, [12] = 0.6, [14] = 0.5 } },
	chorus = { k = { [0] = 1, [2] = 0.6, [8] = 0.7, [10] = 0.7 }, s = { [4] = 1, [12] = 1 }, h = { [0] = 0.7, [2] = 0.55, [4] = 0.7, [6] = 0.55, [8] = 0.7, [10] = 0.55, [12] = 0.7, [14] = 0.55 } },
	outro = { k = { [0] = 1 }, s = { [4] = 0.7, [12] = 0.7 }, h = { [0] = 0.5, [4] = 0.5, [8] = 0.5, [12] = 0.5 } },
}

local FILL_PATTERNS = {
	-- slot, drum
	{ { 10, "snare" }, { 11, "tom1" }, { 12, "tom1" }, { 13, "tom2" }, { 14, "floor" }, { 15, "floor" } },
	{ { 12, "tom1" }, { 13, "tom1" }, { 14, "tom2" }, { 15, "floor" } },
	{ { 8, "snare" }, { 10, "tom1" }, { 11, "tom2" }, { 12, "tom2" }, { 13, "floor" }, { 14, "floor" }, { 15, "snare" } },
}

local function buildDrums(song: any, seed: number, sections: { Section }, slotDur: number): { DrumEvent }
	local ev: { DrumEvent } = {}
	local spb = song.slotsPerBar
	local sectionStartBars: { [number]: Section } = {}
	for _, s in sections do
		sectionStartBars[s.startBar] = s
	end
	local lastSectionBar = sections[#sections].startBar
	for bar = 0, song.bars - 1 do
		local ln = song.lanes[bar + 1]
		local sec = nil
		for _, s in sections do
			if bar >= s.startBar and bar < s.endBar then
				sec = s
			end
		end
		local kind = sec and sec.kind or "verse"
		local prior = PRIOR[kind] or PRIOR.verse
		-- bir sonraki ölçü yeni bölüm mü / 4 ölçülük cümle sonu: fill adayı
		local nextIsSection = sectionStartBars[bar + 1] ~= nil
		local isFillBar = nextIsSection and bar + 1 < song.bars and kind ~= "outro"
			or (kind == "chorus" and bar % 8 == 7 and Rng.chance(seed, bar, 11, 0.6))
		local fillSlot0 = 99
		local fillList
		if isFillBar then
			fillList = FILL_PATTERNS[1 + math.floor(Rng.hash(seed, bar, 5) * #FILL_PATTERNS)]
			fillSlot0 = fillList[1][1]
		end
		local barBase = bar * spb
		for slot = 0, spb - 1 do
			local gslot = barBase + slot
			local t = song.firstBarTime + gslot * slotDur
			if slot < fillSlot0 then
				local kv = math.max((prior.k[slot] or 0) * 0.7, lane(ln.k, slot))
				-- backbeat/ana vuruşlarda ölçüm düşükse bile stil kazansın (distorsiyon masker)
				if kv >= 0.42 then
					table.insert(ev, { t = t, slot = gslot, kind = "kick", str = math.clamp(kv, 0.45, 1), drum = "kick" })
				end
				local sv = math.max((prior.s[slot] or 0) * 0.75, lane(ln.s, slot))
				if sv >= 0.45 and (slot % 4 == 0 or lane(ln.s, slot) >= 0.55) then
					local ghost = (prior.s[slot] == nil) and sv < 0.7
					table.insert(ev, { t = t, slot = gslot, kind = "snare", str = ghost and 0.3 or math.clamp(sv, 0.55, 1), drum = "snare" })
				end
				-- crash: ölçüm yüksek ya da bölüm başı
				local isSecStart = slot == 0 and sectionStartBars[bar] ~= nil and bar > 0
				local cv = lane(ln.c, slot)
				if isSecStart or cv >= 0.55 then
					table.insert(ev, { t = t, slot = gslot, kind = "crash", str = isSecStart and 1.0 or 0.8, drum = "crash" })
				else
					-- hi-hat / ride: bölüm yoğunluğuna göre
					local hv = math.max((prior.h[slot] or 0) * 0.8, lane(ln.h, slot))
					local ride = kind == "chorus" and bar % 8 >= 4
					if hv >= 0.45 and (slot % 2 == 0 or lane(ln.h, slot) >= 0.65) then
						local open = lane(ln.h, slot) >= 0.9 and slot % 4 == 2
						table.insert(ev, {
							t = t, slot = gslot, kind = ride and "ride" or (open and "hatOpen" or "hat"),
							str = math.clamp(hv, 0.4, 1) * (slot % 4 == 0 and 1 or 0.78), drum = ride and "ride" or "hat",
						})
					end
				end
			end
		end
		if fillList then
			for i, f in fillList do
				local gslot = barBase + f[1]
				local str = 0.62 + 0.38 * (i / #fillList)
				table.insert(ev, {
					t = song.firstBarTime + gslot * slotDur, slot = gslot, kind = f[2] == "snare" and "snare" or "tom",
					str = str, drum = f[2], fill = true,
				})
			end
			-- fill'den sonraki bölüm başı için kick yok: ana vuruşta crash+kick (bir sonraki ölçüde üretilir)
		end
	end
	table.sort(ev, function(a, b)
		if a.t ~= b.t then
			return a.t < b.t
		end
		return a.kind < b.kind
	end)
	-- ── el ataması + FİZİKSEL UYGULANABİLİRLİK ──
	-- Her el için iki vuruş arası en az  t_min = 0.07 + mesafe/hız  sn gerekir (kol hızı sınırlı). Hızlı fill'de eller
	-- dönüşümlü kullanılır; hiçbir elin yetişemeyeceği vuruş atılır (insan zaten çalamaz) - öncelik: crash > tom/snare > ride > hat.
	local ALLOWED = {
		hat = { "Right" }, hatOpen = { "Right" }, ride = { "Right" }, crash = { "Left" },
		snare = { "Left", "Right" }, tom1 = { "Left", "Right" }, tom2 = { "Right", "Left" }, floor = { "Right" },
	}
	local PRIO = { crash = 5, tom = 4, snare = 4, ride = 3, hatOpen = 3, hat = 2 }
	local function drumPos(e: DrumEvent): Vector3
		local name = e.drum == "hatOpen" and "hat" or e.drum
		return DrumKit.PIECES[name].center
	end
	local HAND_SPEED = 7.5 -- stud/sn (referans birim: kit ölçeği)
	local out: { DrumEvent } = {}
	local last: { [string]: { e: DrumEvent, idx: number }? } = { Left = nil, Right = nil }
	for _, e in ev do
		if e.drum == "kick" then
			table.insert(out, e)
		else
			local cand = ALLOWED[e.drum] or { "Left" }
			local best, bestShort = nil, 1e9
			for _, h in cand do
				local l = last[h]
				local short = 0
				if l then
					local need = 0.07 + (drumPos(l.e) - drumPos(e)).Magnitude / HAND_SPEED
					short = math.max(0, need - (e.t - l.e.t))
				end
				if short < bestShort - 1e-9 then
					best, bestShort = h, short
				end
			end
			if bestShort <= 0.02 then
				e.hand = best
				table.insert(out, e)
				last[best] = { e = e, idx = #out }
			else
				-- yetişemiyor: daha öncelikli ise öncekini at, değilse bunu at
				local l = last[best]
				if l and (PRIO[e.kind] or 0) > (PRIO[l.e.kind] or 0) then
					l.e.hand = nil
					l.e.dropped = true
					e.hand = best
					table.insert(out, e)
					last[best] = { e = e, idx = #out }
				end
			end
		end
	end
	local keep: { DrumEvent } = {}
	for _, e in out do
		if not e.dropped then
			table.insert(keep, e)
		end
	end
	return keep
end

-- ───── gitar ─────
-- pc -> (tel, perde): E (6. tel) ve A (5. tel) üzerinde power chord kökü. Önceki konuma en yakın olanı seç.
local function powerChordFret(pc: number, prevFret: number): (number, number)
	local fE = (pc - 4) % 12
	local fA = (pc - 9) % 12
	local candE = { fret = fE, string = 6 }
	local candA = { fret = fA, string = 5 }
	local best = candE
	local function cost(c)
		return math.abs(c.fret - prevFret) + (c.fret > 9 and 3 or 0) + (c.fret == 0 and -0.5 or 0)
	end
	if cost(candA) < cost(candE) then
		best = candA
	end
	return best.fret, best.string
end

local function buildChords(song: any, slotDur: number, barDur: number): { ChordEvent }
	local out: { ChordEvent } = {}
	local prevFret, prevPc = 5, -1
	for h, c in song.chords do
		local pc, q = c[1], c[2]
		if pc ~= prevPc then
			local fret, str = powerChordFret(pc, prevFret)
			local bar = math.floor((h - 1) / 2)
			table.insert(out, {
				t = song.firstBarTime + (h - 1) * barDur / 2, bar = bar, pc = pc, quality = q, fret = fret, string = str,
			})
			prevFret, prevPc = fret, pc
		end
	end
	return out
end

local function buildGuitar(song: any, seed: number, sections: { Section }, slotDur: number): { StrumEvent }
	-- El her zaman 8'lik ızgarada aşağı-yukarı sallanır (gerçek gitaristte kol durmaz); sesli olan ya da
	-- "hayalet" (sessiz) vuruş olarak işaretlenir. Aşağı = vuruş başı, yukarı = "ve". Yön her zaman dönüşümlü.
	local out: { StrumEvent } = {}
	local spb = song.slotsPerBar
	for bar = 0, song.bars - 1 do
		local ln = song.lanes[bar + 1]
		local sec
		for _, s in sections do
			if bar >= s.startBar and bar < s.endBar then
				sec = s
			end
		end
		local kind = sec and sec.kind or "verse"
		local cycle = math.floor(bar / 4) % 4
		for slot = 0, spb - 1, 2 do
			local down = slot % 4 == 0
			local dir = down and 1 or -1
			local g = math.max(lane(ln.g, slot), lane(ln.g, slot + 1) * 0.8)
			local str = 0.4 + 0.6 * g
			local k = down and "down" or "up"
			if slot == 0 then
				str = math.max(str, 0.9)
				k = "accent"
			elseif slot == 8 then
				str = math.max(str, 0.75)
			end
			if g >= 0.8 and slot ~= 0 then
				k = "accent"
			end
			-- yukarı vuruş sakin bölümlerde çoğunlukla hayalet
			local quiet = kind == "intro" or kind == "outro" or kind == "calm"
			if not down and g < (quiet and 0.6 or 0.25) then
				k = "ghost"
				str = 0.2
			end
			if quiet and slot % 8 ~= 0 and g < 0.5 then
				k = "ghost"
				str = 0.2
			end
			-- muted (palm mute) "chug": döngü 3'te vurgusuz vuruşlar
			if kind ~= "chorus" and cycle == 2 and k ~= "accent" and k ~= "ghost" and g < 0.4 then
				k = "mute"
				str = math.min(str, 0.45)
			end
			-- cümle sonunda kısa boşluk: ses kesilir, kol sallanmaya devam eder
			if (bar % 4 == 3) and slot >= 12 and Rng.chance(seed, bar, slot, 0.6) then
				k = "ghost"
				str = 0.2
			end
			table.insert(out, {
				t = song.firstBarTime + (bar * spb + slot) * slotDur, slot = bar * spb + slot,
				dir = dir, str = str, kind = k,
			})
		end
	end
	return out
end

-- ───── bas ─────
local OPEN = { 23, 28, 33, 38, 43 } -- 5 telli: B0 E1 A1 D2 G2

local function snapToChord(midi: number, chordPc: number?): number
	if midi == 0 or chordPc == nil then
		return midi
	end
	-- kök/beşli/oktav perdelerine yakın en yakın nota (±1 yarım ton içinde)
	local allowed = { chordPc, (chordPc + 7) % 12, (chordPc + 3) % 12, (chordPc + 4) % 12 }
	local best, bestD = midi, 99
	for _, pc in allowed do
		for oct = -1, 6 do
			local m = pc + 12 * oct
			local d = math.abs(m - midi)
			if d < bestD then
				best, bestD = m, d
			end
		end
	end
	return bestD <= 1 and best or midi
end

local function bassPosition(midi: number, prevString: number, prevFret: number): (number, number)
	local bestS, bestF, bestCost = 2, 0, 1e9
	for s, open in OPEN do
		local fret = midi - open
		if fret >= 0 and fret <= 12 then
			local cost = math.abs(fret - prevFret) + 0.25 * fret + 0.4 * math.abs(s - prevString) + (fret > 7 and 2 or 0)
			if cost < bestCost then
				bestS, bestF, bestCost = s, fret, cost
			end
		end
	end
	return bestS, bestF
end

local function buildBass(song: any, seed: number, sections: { Section }, slotDur: number): { BassEvent }
	local out: { BassEvent } = {}
	local spb = song.slotsPerBar
	local prevS, prevF = 2, 3
	local finger = 1
	for bar = 0, song.bars - 1 do
		local ln = song.lanes[bar + 1]
		local sec
		for _, s in sections do
			if bar >= s.startBar and bar < s.endBar then
				sec = s
			end
		end
		local kind = sec and sec.kind or "verse"
		local half1, half2 = song.chords[bar * 2 + 1], song.chords[bar * 2 + 2]
		for slot = 0, spb - 1 do
			local beat = math.floor(slot / 4)
			local midiRaw = song.bass[bar * 4 + beat + 1] or 0
			local chord = (slot < 8) and half1 or half2
			local midi = snapToChord(midiRaw, chord and chord[1] or nil)
			if midi > 0 then
				local kv = lane(ln.k, slot)
				local isBeat = slot % 4 == 0
				local eighth = slot % 2 == 0 and (kind == "chorus") and slot % 4 == 2
				local kickLocked = kv >= 0.6 and slot % 2 == 0
				if isBeat or eighth or kickLocked then
					local string, fret = bassPosition(midi, prevS, prevF)
					prevS, prevF = string, fret
					finger = 3 - finger
					local str = isBeat and (slot == 0 and 0.95 or 0.8) or (kickLocked and 0.75 or 0.55)
					table.insert(out, {
						t = song.firstBarTime + (bar * spb + slot) * slotDur, slot = bar * spb + slot, midi = midi,
						str = str, string = string, fret = fret, dur = slotDur * 2, finger = finger,
					})
				end
			end
		end
	end
	-- süreleri bir sonraki notaya kadar uzat (en fazla 1 ölçü)
	for i, e in out do
		local nxt = out[i + 1]
		e.dur = nxt and math.min(nxt.t - e.t, slotDur * 16) or slotDur * 4
	end
	return out
end

-- ───── ölçü stilleri: tekrar hissini kırmak için kontrollü varyasyon ─────
local function buildBarStyles(song: any, seed: number, sections: { Section }): { BarStyle }
	local out: { BarStyle } = {}
	for bar = 0, song.bars - 1 do
		local cycle = math.floor(bar / 4) % 4
		local phase = bar % 4
		local sec
		for _, s in sections do
			if bar >= s.startBar and bar < s.endBar then
				sec = s
			end
		end
		local kind = sec and sec.kind or "verse"
		local sectionLast = sec ~= nil and bar == sec.endBar - 1
		local vocalOn = false
		if kind == "verse" or kind == "calm" then
			vocalOn = phase ~= 3
		elseif kind == "chorus" then
			vocalOn = true
		end
		-- Aynı 4 ölçülük riff her tekrarlandığında kontrollü varyasyon (rastgele değil, döngü numarasına bağlı):
		--   döngü 1: normal sallanma | döngü 2: daha güçlü vurgular, daha çok çökme | döngü 3: kafa hareketi öne çıkar
		--   döngü 4: duruş değişimi (ağırlık, geniş sallanma). Küçük bir (%±8) deterministik oynama tekrarı kırar.
		local jitter = 0.92 + 0.16 * Rng.hash(seed, math.floor(bar / 4), 9)
		local SWAY = { 1.0, 1.1, 0.9, 1.5 }
		local BOUNCE = { 1.0, 1.3, 1.0, 0.9 }
		local LEAN = { 1.0, 1.25, 0.75, 1.1 }
		local HEAD = { 1.0, 1.0, 1.6, 1.2 }
		local ACCENT = { 1.0, 1.3, 1.0, 1.1 }
		table.insert(out, {
			bar = bar, cycle = cycle, phase = phase,
			accentBoost = ACCENT[cycle + 1] * jitter,
			headAmp = HEAD[cycle + 1] * jitter,
			swayMul = SWAY[cycle + 1] * jitter,
			bounceMul = BOUNCE[cycle + 1] * jitter,
			leanMul = LEAN[cycle + 1],
			stanceShift = cycle == 3 and phase == 0, -- döngü 4: duruş değişimi
			fill = sectionLast or (phase == 3 and cycle == 3),
			hold = phase == 3 and Rng.chance(seed, bar, 3, 0.35), -- pose hold: son vuruş sonrası kısa donuk poz
			swayDir = Rng.hash(seed, math.floor(bar / 2), 17) < 0.5 and -1 or 1,
			vocalOn = vocalOn,
		})
	end
	return out
end

function Score.barStyle(self: Score, bar: number): BarStyle
	local i = math.clamp(math.floor(bar), 0, #self.barStyles - 1)
	return self.barStyles[i + 1]
end

function Score.build(song: any, seed: number?): Score
	local sd = seed or 20240601
	local beatDur = 60 / song.bpm
	local barDur = beatDur * song.beatsPerBar
	local slotDur = barDur / song.slotsPerBar
	local sections = buildSections(song, slotDur, barDur)
	local self = {
		song = song, seed = sd, slotDur = slotDur, barDur = barDur, beatDur = beatDur,
		sections = sections,
		drums = buildDrums(song, sd, sections, slotDur),
		guitar = buildGuitar(song, sd, sections, slotDur),
		chords = buildChords(song, slotDur, barDur),
		bass = buildBass(song, sd, sections, slotDur),
		barStyles = buildBarStyles(song, sd, sections),
	}
	return (setmetatable(self, { __index = Score }) :: any) :: Score
end

-- Zamana göre sıralı bir olay listesinde ilk indeks: t >= time (ikili arama)
function Score.firstIndexAtOrAfter(list: { { t: number } }, time: number): number
	local lo, hi = 1, #list + 1
	while lo < hi do
		local mid = (lo + hi) // 2
		if list[mid].t < time then
			lo = mid + 1
		else
			hi = mid
		end
	end
	return lo
end

-- Zaman aralığı (a, b] içindeki olaylar (ardışık karelerde her olay tam bir kez tetiklenir)
function Score.eventsIn(list: { { t: number } }, a: number, b: number): { any }
	local out = {}
	local i = Score.firstIndexAtOrAfter(list, a + 1e-9)
	while i <= #list and list[i].t <= b do
		table.insert(out, list[i])
		i += 1
	end
	return out
end

-- Belirli bir zamandan sonraki n. olay (öngörü / anticipation için)
function Score.nextAfter(list: { { t: number } }, time: number, n: number?): any?
	local i = Score.firstIndexAtOrAfter(list, time + 1e-9) + ((n or 1) - 1)
	return list[i]
end

return Score
