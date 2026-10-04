-- Sahne önizlemesi: 4 karakter sahne yerleşiminde (SCENE=band ile çalışır). LOG_FILE'a JSON kareleri yazar.
if not (R.env and R.env.SCENE == "band") then return end
local Rbx = R.Rbx
local Band = require(R.Root)
local T0 = tonumber(R.env.T0) or 20
local T1 = tonumber(R.env.T1) or 21
local STEP = tonumber(R.env.STEP) or 3

local function f(x) return string.format("%.3f", x) end
local function v(p) return "[" .. f(p.X) .. "," .. f(p.Y) .. "," .. f(p.Z) .. "]" end

local container = Rbx.newInstance("Folder", "Band")
-- sahne: izleyici -Z tarafında; karakterler -Z'ye (izleyiciye) bakar. Boyunlar içe baksın diye gitar +X'te, bas -X'te; vokal önde, bateri arkada.
local layout = {
	{ "Gitarist", 5.5, 0.0, math.rad(18) }, -- boyun gruba (içe) bakar
	{ "Basgitar", -5.5, 0.0, math.rad(-22) },
	{ "Vokalist", 0.0, -2.5, 0 },
	{ "Baterist", 0.0, 6.0, 0 },
}
for _, n in ipairs(layout) do
	local m = R.mockR15({ name = n[1] })
	local cf = CFrame.new(n[2], 3, n[3]) * CFrame.Angles(0, n[4], 0)
	for _, p in ipairs(m:GetChildren()) do p.CFrame = cf * p.CFrame end
	m.Humanoid = nil
	Rbx.parent(m, container)
end
local timeSrc, setTime = Band.manualTimeSource()
local band = Band.new({ container = container, timeSource = timeSrc, buildProps = false })
local dt = 1 / 60
local t = T0 - 2
setTime(t)
local frame = 0
while t < T1 do
	t += dt
	setTime(t)
	band:update(dt)
	frame += 1
	if t >= T0 and frame % STEP == 0 then
		local per = {}
		for _, role in ipairs(band.order) do
			local perf = band.performers[role]
			local parts = perf.parts
			local j = {}
			for _, name in ipairs(perf.rig.order) do
				local jj = perf.rig.joints[name]
				table.insert(j, '"' .. name .. '":' .. v((parts[jj.part0] * jj.c0).Position))
			end
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
			table.insert(per, '"' .. role .. '":{"j":{' .. table.concat(j, ",") .. '},"head":' .. v(parts.Head.Position) .. ',' .. table.concat(hands, ",") .. ',"geo":[' .. table.concat(geo, ",") .. ']}')
		end
		print('DUMP {"t":' .. f(t) .. ',"performers":{' .. table.concat(per, ",") .. '}}')
	end
end
