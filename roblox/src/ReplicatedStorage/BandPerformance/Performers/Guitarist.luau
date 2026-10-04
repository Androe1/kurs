--!strict
--[[ Gitarist: Performer + Stringed("Guitar"). Fabrika: Guitarist.create(rig, {score, clock, seed}) ]]

local Root = script:FindFirstAncestor("BandPerformance")
local Performer = require(Root.Performers.Performer)
local Stringed = require(Root.Performers.Stringed)

local Guitarist = {}

function Guitarist.create(rig: any, opts: { score: any, clock: any, seed: number? })
	return Performer.new(rig, "Guitar", {
		score = opts.score, clock = opts.clock, seed = opts.seed,
		instrument = function(perf)
			return Stringed.new(perf, "Guitar")
		end,
	})
end

return Guitarist
