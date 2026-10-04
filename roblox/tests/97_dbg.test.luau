local Song = require(R.Root.Data.SongMap)
local Score = require(R.Root.Music.Score)
local Clock = require(R.Root.Music.Clock)
local R15Rig = require(R.Root.Rig.R15Rig)
local Vocalist = require(R.Root.Performers.Vocalist)
local score = Score.build(Song, 3)
local clock = Clock.new(Song, 0)
local rig = R15Rig.new(R.mockR15({ name = "D" }))
local perf = require(R.Root.Performers.Drummer).create(rig, { score = score, clock = clock })
local L = perf.instrument
local dt = 1 / 60
clock:seek(163.2)
for i = 1, 30 do
	clock:update(dt, nil, true)
	perf:update(dt)
	local ax, ang = perf.lastTr.RightWrist:ToAxisAngle()
	local ax2, ang2 = perf.lastTr.RightElbow:ToAxisAngle()
	local ax3, ang3 = perf.lastTr.RightShoulder:ToAxisAngle()
	local tip, hh, AA, pp, aa, bb = L:sampleHand("Right", clock.time)
	print(string.format("   tip %s h=%.2f A=%.2f p=%.2f a=%s@%.2f b=%s@%.2f", tostring(tip), hh, AA, pp, aa and aa.kind or "-", aa and aa.t or 0, bb and bb.kind or "-", bb and bb.t or 0))
	print(string.format("t=%.3f wrist %3.0f° ax(%s) elbow %3.0f° ax(%s) shoulder %3.0f° ikW %.2f", clock.time, math.deg(ang), tostring(ax), math.deg(ang2), tostring(ax2), math.deg(ang3), perf.ikSpring.Right.x))
end
