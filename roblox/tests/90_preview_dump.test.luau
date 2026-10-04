-- Önizleme verisi üretir (LOG_FILE ile dosyaya yazılır): her karede iskelet + enstrüman geometrisi (JSON satırı)
local T = R.T
local Song = require(R.Root.Data.SongMap)
local Score = require(R.Root.Music.Score)
local Clock = require(R.Root.Music.Clock)
local R15Rig = require(R.Root.Rig.R15Rig)

local ROLE = R.env and R.env.ROLE
if not ROLE then return end
local T0 = tonumber(R.env and R.env.T0) or 9.0
local T1 = tonumber(R.env and R.env.T1) or 12.0
local STEP = tonumber(R.env and R.env.STEP) or 2

local function f(x) return string.format("%.3f", x) end
local function v(p) return "[" .. f(p.X) .. "," .. f(p.Y) .. "," .. f(p.Z) .. "]" end

local factories = {
	Guitar = function() return require(R.Root.Performers.Guitarist) end,
	Bass = function() return require(R.Root.Performers.Bassist) end,
	Drums = function() return require(R.Root.Performers.Drummer) end,
	Vocal = function() return require(R.Root.Performers.Vocalist) end,
}
if not factories[ROLE] then return end -- yalnızca ROLE verilen preview'larda çalışır
local Factory = factories[ROLE]()
local score = Score.build(Song, 3)
local clock = Clock.new(Song, 0)
local model = R.mockR15({ name = ROLE })
local rig = R15Rig.new(model)
local perf = Factory.create(rig, { score = score, clock = clock })

local dt = 1 / 60
clock:seek(T0 - 2.0)
local frame = 0
local lines = {}
local minErr, maxErr = 0, 0
local sumErr, nErr = 0, 0
while clock.rawTime < T1 do
	clock:update(dt, nil, true)
	perf:update(dt)
	frame += 1
	if clock.rawTime >= T0 and frame % STEP == 0 then
		local parts = perf.parts
		local j = {}
		for _, name in ipairs(rig.order) do
			local jj = rig.joints[name]
			table.insert(j, '"' .. name .. '":' .. v((parts[jj.part0] * jj.c0).Position))
		end
		local head = parts.Head.Position
		local hands = {}
		for _, side in ipairs({ "Left", "Right" }) do
			local h = parts[side .. "Hand"]
			table.insert(hands, '"' .. side .. 'Tip":' .. v(h * Vector3.new(0, -0.45, 0)))
			table.insert(hands, '"' .. side .. 'Palm":' .. v(h:VectorToWorldSpace(Vector3.new(side == "Left" and 1 or -1, 0, 0))))
		end
		local geo = {}
		if perf.instrument and perf.instrument.debugGeometry then
			for _, poly in ipairs(perf.instrument:debugGeometry()) do
				local pts = {}
				for _, p in ipairs(poly.pts) do table.insert(pts, v(p)) end
				table.insert(geo, '{"c":"' .. poly.color .. '","p":[' .. table.concat(pts, ",") .. ']}')
			end
		end
		local he = perf.metrics.handError
		sumErr += he.Left + he.Right nErr += 2
		maxErr = math.max(maxErr, he.Left, he.Right)
		print("DUMP " .. '{"t":' .. f(clock.rawTime) .. ',"state":"' .. perf.state .. '","j":{' .. table.concat(j, ",") .. '},"head":' .. v(head) .. ',' .. table.concat(hands, ",") .. ',"geo":[' .. table.concat(geo, ",") .. '],"err":[' .. f(he.Left) .. ',' .. f(he.Right) .. '],"reach":[' .. f(perf.metrics.reach.Left or 0) .. ',' .. f(perf.metrics.reach.Right or 0) .. ']}')
	end
end
print(string.format("  [%s] temas hatası ort %.4f, maks %.4f stud (%d örnek)", ROLE, sumErr / math.max(nErr, 1), maxErr, nErr))
