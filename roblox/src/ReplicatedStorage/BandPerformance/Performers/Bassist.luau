--!strict
--[[ Basçı: Performer + Stringed("Bass"). Gitardan farklı: ağır groove, parmak pluck, sakin sağ el. ]]

local Root = script:FindFirstAncestor("BandPerformance")
local Performer = require(Root.Performers.Performer)
local Stringed = require(Root.Performers.Stringed)

local Bassist = {}

function Bassist.create(rig: any, opts: { score: any, clock: any, seed: number? })
	return Performer.new(rig, "Bass", {
		score = opts.score, clock = opts.clock, seed = opts.seed,
		instrument = function(perf)
			return Stringed.new(perf, "Bass")
		end,
	})
end

return Bassist
