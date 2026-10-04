local Song = require(R.Root.Data.SongMap)
local Score = require(R.Root.Music.Score)
local Clock = require(R.Root.Music.Clock)
local R15Rig = require(R.Root.Rig.R15Rig)
local role = R.env.ROLE
local FACT = {
	Guitar = require(R.Root.Performers.Guitarist), Bass = require(R.Root.Performers.Bassist),
	Drums = require(R.Root.Performers.Drummer), Vocal = require(R.Root.Performers.Vocalist),
}
local score = Score.build(Song, 3)
local clock = Clock.new(Song, 0)
local rig = R15Rig.new(R.mockR15({ name = role }))
local perf = FACT[role].create(rig, { score = score, clock = clock })
local dt = 1 / 60
local prev = {}
local thr = tonumber(R.env.THR) or 30
local reports = 0
while clock.rawTime < 172 and reports < 12 do
	clock:update(dt, nil, true)
	perf:update(dt)
	for _, side in ipairs({ 'Left', 'Right' }) do
		local he = perf.metrics.handError[side]
		if he > 0.12 and (R.env.HE == '1') then reports += 1 print(string.format('t=%.3f handErr %s %.3f state %s reach %.3f ikW %.2f', clock.time, side, he, perf.state, perf.metrics.reach[side], perf.ikSpring[side].x)) end
	end
	for name, cf in pairs(perf.lastTr) do
		local pr = prev[name]
		if pr then
			local _, a = (pr:Inverse() * cf.Rotation):ToAxisAngle()
			if math.deg(a) > thr then
				reports += 1
				print(string.format("t=%.3f %-14s Δ=%.0f° handErr L%.3f R%.3f state %s", clock.time, name, math.deg(a), perf.metrics.handError.Left, perf.metrics.handError.Right, perf.state))
			end
		end
		prev[name] = cf.Rotation
	end
end
