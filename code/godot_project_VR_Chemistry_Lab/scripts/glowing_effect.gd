extends OmniLight3D

## How restless the flicker looks at targetIntensity == 1.0.
## (At other intensities this scales automatically, see setTargetIntensity)
@export var baseFlickerAmount: float = 0.001
@export var baseFlickerLikelihood: float = 0.5

## How fast the glow adapts to a new target intensity (per second).
@export var risingSpeed: float = 1.5

## How far the flicker is allowed to deviate from its current "center",
## as a multiple of howMuchMore. Prevents light_energy from drifting away unbounded.
@export var flickerRangeInStepUnits: float = 20.0

## How long the glow lives at strength == 1.0. Scaled by strength in
## startDuration() - stronger reactions glow noticeably longer, weaker
## ones flicker out fast. This is the actual, normal way the effect ends
## now (see startDuration() and _process()); the Timer/_on_timer_timeout
## below stays a pure safety net, unrelated to this.
@export var baseDurationSeconds: float = 4.0

## Counts down to 0 once startDuration() has been called; -1.0 means "not
## started yet" and disables the countdown.
var remainingDuration: float = -1.0

var gettingMore: bool = true
var howLikely: float = 0.5
var howMuchMore: float = 0.001

var active: bool = true

## True once a fade-out has been triggered (either the duration ran out or
## deactivate() was called from outside). While true, targetIntensity is 0
## and _process() waits for baseLightEnergy/light_energy to actually reach
## ~0 before really shutting the light down - this is what makes the glow
## fade out smoothly instead of cutting off abruptly.
var fadingOut: bool = false

## Emitted once the fade-out has fully finished and this node is about to
## queue_free() itself. reaction_handler.gd listens to this to remove its
## entry from the `effects` dictionary - without that, the dictionary entry
## would stay forever and a reaction that glowed once could never glow again.
signal effectFinished()

## Set from outside (reaction_handler.gd), from the reaction's
## reactionStrength as looked up in DataSynchronizer.reactionRegistry.
## 0.0 = barely visible glow, 1.0 = reference/full intensity.
## Values > 1.0 are allowed for especially violent reactions.
var targetIntensity: float = 0.0: set = setTargetIntensity

## The center the flicker mechanism is currently oscillating around.
## Approaches targetIntensity continuously instead of jumping.
var baseLightEnergy: float = 0.0

func _process(delta: float) -> void:
	if(active):
		baseLightEnergy = move_toward(baseLightEnergy, targetIntensity, risingSpeed * delta)
		
		if(randf() < howLikely):
			gettingMore = !gettingMore
		if(gettingMore):
			self.light_energy += howMuchMore
		else:
			self.light_energy -= howMuchMore

		# Keep the flicker close to the current "center" instead of drifting away
		# unbounded - that was the actual problem with the old script (light_energy
		# just kept growing forever, regardless of any reaction strength).
		var flickerRange = howMuchMore * flickerRangeInStepUnits
		self.light_energy = clamp(self.light_energy, max(0.0, baseLightEnergy - flickerRange), baseLightEnergy + flickerRange)

	# This is what actually ends the glow now. remainingDuration is only
	# ever set once, in startDuration() - NOT here and NOT in
	# setTargetIntensity(), even though that gets called every frame while
	# the reaction is ongoing. Ticking it down purely from delta (instead
	# of re-deriving/resetting it from the current intensity each frame)
	# means a reaction that keeps sending more updates does not extend the
		# glow - only its strength at the moment the glow started does.
		if(remainingDuration >= 0.0):
			remainingDuration -= delta
			if(remainingDuration <= 0.0 and not fadingOut):
				_startFadeOut()

	# Once a fade-out was triggered, wait until the light has actually
	# reached (near) zero - via the normal move_toward()/flicker above,
	# same speed as fading in - before really shutting it down. This is
	# what makes the glow fade out smoothly instead of an abrupt cut.
	if(fadingOut and baseLightEnergy <= 0.01 and light_energy <= 0.01):
		_finishFadeOut()

func _startFadeOut() -> void:
	fadingOut = true
	self.targetIntensity = 0.0

func _finishFadeOut() -> void:
	active = false
	self.light_energy = 0.0
	effectFinished.emit()
	queue_free()

## Starts the countdown to when this glow ends, based on the reaction's
## strength at the moment the effect was spawned (see
## reaction_handler.gd's _instandiateEffectsNeeded). Call this exactly
## once, right after instantiating the effect - calling it again later
## (e.g. every frame) would keep resetting the countdown and the glow
## would never end, same bug as before with the old Timer.
func startDuration(strength: float) -> void:
	remainingDuration = baseDurationSeconds * (0.5 + max(0.0, strength))

## Sets the target intensity from outside. Also scales the flicker itself -
## a strong reaction shouldn't just glow brighter, it should flicker more lively too.
func setTargetIntensity(newIntensity: float) -> void:
	targetIntensity = max(0.0, newIntensity)
	howMuchMore = baseFlickerAmount * (0.5 + targetIntensity)
	howLikely = baseFlickerLikelihood

func _on_timer_timeout() -> void:
	# Safety net only, NOT the normal way this effect ends - reaction_handler.gd
	# now actively queue_free()s this node the moment _reactionShouldGlow()
	# goes false (see _freeEffectsIfNoLongerNeeded there), so this should
	# basically never fire during normal play. If it does, something didn't
	# get cleaned up properly - freeing here is a fallback against a leaked
	# light, not a way to time a reaction's glow duration.
	#
	# Set this Timer's wait_time generously in the editor (e.g. several
	# minutes) and one_shot = true / autostart = true. It must NOT be
	# restarted anywhere - a restarted or short Timer is what caused
	# reactions that simply took longer to finish to look brighter/lit for
	# longer, independent of their actual reactionStrength.
	push_warning("glowing_effect.gd: safety-net Timer fired - reaction_handler.gd should have freed this effect already")
	deactivate() # fades out smoothly, same as the normal end-of-duration path

## Called from outside (reaction_handler.gd, once the reaction no longer
## needs to glow) or from the safety-net Timer below. Just triggers the
## same smooth fade-out as a normal duration end - no more instant cutoff.
## Safe to call multiple times; fadingOut guards against restarting it.
func deactivate():
	if(not fadingOut):
		_startFadeOut()
