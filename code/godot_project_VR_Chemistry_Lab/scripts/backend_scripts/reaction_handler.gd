extends Node

@onready var effect = preload( "res://effects/glowing_effect.tscn" )
var reactionData: Node
var serverHandler: Node
var world: Node
var justStartedHeating: bool = false: set=setJustStartedHeating
var justStoppedHeating: bool = false: set=setJustStoppedHeating
var effects: Dictionary = {}
## Remembers reactionData.getCompositionVersion() as it was at the moment
## the last glow effect was ignited. Ignition is only allowed again once
## this differs from the current version - i.e. Na was actually taken out
## and/or put back in since then - not just because the previous effect's
## own duration ran out while the composition stayed exactly the same
## (that alone used to cause a repeated flicker: extinguish -> effects
## dict empties out -> immediately re-ignite -> repeat).
var lastIgnitedCompositionVersion: int = -1
var simulationData: Array: set=setSimulationData
const SIMULATION_PLAYBACK_DELAY_SECONDS: float = 0.5
const REQUEST_MORE_DATA_MARGIN_SECONDS: float = 0.5

# --- Glow intensity from reaction strength ---
# The glow intensity is now a fixed, rough value looked up per reaction from
# DataSynchronizer.reactionRegistry (see data/reaction_registry.gd), instead
# of being derived from how fast the temperature rises. glowing_effect.gd
# already smooths any change towards targetIntensity on its own (risingSpeed),
# so no extra smoothing is needed here.

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	reactionData = $reactionData
	serverHandler = $server_handler
	world = get_tree().current_scene
	_connectToSignals()

func _connectToSignals() -> void:
	DataSynchronizer.connect("dataChanged", Callable(self, "_on_data_changed"))

# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(_delta: float) -> void:
	var whatReaction = reactionData.getWhatReaction()
	var reactionIds = reactionData.getReactionIDs()
	if(justStoppedHeating and serverHandler.hasInitializedReaction() and serverHandler.isReactionInitialized(serverHandler.getInitializedReaction(), reactionIds)):
		# One-shot: send the final stop-heating step, then clear the flag -
		# but only once it actually went out. requestStopHeatingAndReactionStep
		# returns false and sends nothing while serverIsBusy (a previous
		# request is still in flight) - clearing the flag anyway would lose
		# the stop-heating request silently, forever. Retry next frame instead.
		if(stopHeatingAndRequestReactionStep(serverHandler.getInitializedReaction())):
			justStoppedHeating = false
	elif(reactionData.reactionDetected()):
		if(justStoppedHeating and serverHandler.hasInitializedReaction()):
			justStoppedHeating = false
		if(not serverHandler.isReactionInitialized(reactionData.getWhatReaction(), reactionData.getReactionIDs())):
			if(initializeReaction(whatReaction, reactionData.getReactionTemperature(), reactionData.getReactionAmountInMol())):
				simulationData = []
			return
		else:
			if(justStartedHeating):
				# Same reasoning as above: requestReactionInit() marks the
				# reaction as initialized as soon as "init" is sent, before
				# the ack comes back - so isReactionInitialized() can already
				# be true while serverIsBusy still is too. The very first
				# attempt to start heating right after init would otherwise
				# be silently dropped and never retried.
				if(startHeatingAndRequestReactionStep(whatReaction)):
					justStartedHeating = false
			elif(justStoppedHeating):
				if(stopHeatingAndRequestReactionStep(whatReaction)):
					justStoppedHeating = false
			else:
				requestReactionStep(whatReaction)
		if(hasDataToAdvance()):
			advanceReactionByTimePassed() #TODO: if correct??



func initializeReaction(whatReaction: String, temperature: float, amountInMol: Dictionary):
	return serverHandler.requestReactionInit(whatReaction, reactionData.getReactionIDs(), temperature, amountInMol)
	
func startHeatingAndRequestReactionStep(whatReaction: String):
	return serverHandler.requestStartHeatingAndReactionStep(whatReaction, reactionData.getReactionIDs())

func stopHeatingAndRequestReactionStep(whatReaction: String):
	return serverHandler.requestStopHeatingAndReactionStep(whatReaction, reactionData.getReactionIDs())

func requestReactionStep(whatReaction: String):
	return serverHandler.requestReactionStep(whatReaction, reactionData.getReactionIDs())
	
func hasDataToAdvance() -> bool:
	return simulationData!=null and simulationData.size()>0 and simulationData[0].size()>0

func advanceReactionByTimePassed() -> void:
	_requestMoreDataIfBufferRunsLow()
	var dataStep: Dictionary = findNextTimestampInCompleteReaction()
	dataStep.set("reactionIds", simulationData[1])
	DataSynchronizer.setStepOfCompleteReaction(dataStep)

func findNextTimestampInCompleteReaction() -> Dictionary:
	var currentAbsolutReactionTime = _getBufferedPlaybackTime()
	for step in simulationData[0]:
		if(step.get("timeStamp") >= currentAbsolutReactionTime):
			return step
	return simulationData[0][-1]

func _getBufferedPlaybackTime() -> float:
	return max(0.0, serverHandler.getCurrentAbsolutReactionTimeInMs() - SIMULATION_PLAYBACK_DELAY_SECONDS)

func _requestMoreDataIfBufferRunsLow() -> void:
	if(not reactionData.reactionDetected()):
		return
	var lastSimulatedTime = (simulationData[0][-1].get("timeStamp")) 
	if(lastSimulatedTime == null):
		lastSimulatedTime = 0
	var bufferedPlaybackTime = _getBufferedPlaybackTime()
	if(lastSimulatedTime - bufferedPlaybackTime <= REQUEST_MORE_DATA_MARGIN_SECONDS):
		requestReactionStep(reactionData.getWhatReaction())

func setJustStartedHeating(newValueForJustStartedHeating: bool) -> void:
	justStartedHeating = newValueForJustStartedHeating

func setJustStoppedHeating(newValueForJustStoppedHeating) -> void:
	justStoppedHeating = newValueForJustStoppedHeating




func setSimulationData(newSimulationData:Array) -> void:
	if(newSimulationData == null or newSimulationData.is_empty()):
		simulationData = []
		return
	if(newSimulationData.size() < 2 or typeof(newSimulationData[1]) != TYPE_DICTIONARY):
		return
	if(not serverHandler.hasInitializedReaction() or not serverHandler.isReactionInitialized(reactionData.getWhatReaction(), newSimulationData[1])):
		print("ReactionHandler: ignoring stale simulation data for another reaction.")
		return
	simulationData = newSimulationData

func _on_data_changed(data:Dictionary) -> void:
	if not _isDataForThisReaction(data):
		return
	if(_effectNeededButNotInstatiated()):
		_instandiateEffectsNeeded()
	elif(_effectNoLongerNeeded()):
		_freeEffectsIfNoLongerNeeded()
	var newReactionPartsNames:Array = _getNewReactionPartsNames(data)
	if(len(newReactionPartsNames) > 0):
		intantiateReactionParts(newReactionPartsNames)

func _isDataForThisReaction(data: Dictionary) -> bool:
	if not data.has("reactionIds"):
		return false
	return serverHandler.isReactionInitialized(reactionData.getWhatReaction(), data.get("reactionIds"))

func _effectNeededButNotInstatiated() -> bool:
	return _reactionShouldGlow() and effects.size()<=0 and reactionData.getCompositionVersion() != lastIgnitedCompositionVersion

func _reactionShouldGlow() -> bool:
	# Whether a reaction glows at all now comes from the registry
	# (reactionStrength > 0.0) instead of a hardcoded "Na" check.
	return DataSynchronizer.getReactionStrength(reactionData.getWhatReaction()) > 0.0

func _effectNoLongerNeeded() -> bool:
	return not _reactionShouldGlow() and effects.size() > 0

func _freeEffectsIfNoLongerNeeded() -> void:
	# Actively tells any still-running effect to fade out the moment the
	# reaction stops glowing (e.g. Na was removed), instead of waiting for
	# its duration timer to run out on its own. deactivate() itself fades
	# smoothly now, it does not cut the light instantly.
	for id in effects.keys():
		var effectNode = effects[id]
		if is_instance_valid(effectNode):
			effectNode.deactivate()
		else:
			effects.erase(id)

func _on_effect_finished(id) -> void:
	# The one place effects actually gets cleaned up. Without this,
	# _effectNeededButNotInstatiated() would keep seeing a stale entry and
	# never let the same reaction glow again after being removed and
	# re-added - that was the original bug.
	effects.erase(id)

func _instandiateEffectsNeeded() -> void:
	 #TODO very temporaray loool: the light is still hardcoded to attach to
	 # the "Na" reaction part - fine as long as only Na-based reactions glow,
	 # but if a future registry entry makes a non-Na-containing reaction glow,
	 # this attachment point needs to become data-driven too.
	var effectNode = effect.instantiate().duplicate()
	var reactionPartForEffect = _getReactionPartForEffect()
	reactionPartForEffect.add_child(effectNode)
	# Gives the effect its strength-scaled lifetime, once, right at spawn -
	# this is what makes it actually end (see startDuration() in
	# glowing_effect.gd). 
	#only the strength at spawn time decides
	# the duration, so a reaction that just keeps sending more updates
	# doesn't stay lit longer because of that alone.
	var reactionStrength = DataSynchronizer.getReactionStrength(reactionData.getWhatReaction())
	effectNode.startDuration(reactionStrength)
	effectNode.targetIntensity = reactionStrength
	var id = reactionPartForEffect.get_instance_id()
	if effects.has(id):
		var oldEffect = effects.get(id)
		if is_instance_valid(oldEffect):
			oldEffect.queue_free()
	effects.set(id, effectNode)
	lastIgnitedCompositionVersion = reactionData.getCompositionVersion()
	# Without this, effects would never get erased from the dictionary -
	# _effectNeededButNotInstatiated() checks effects.size()<=0, so a
	# reaction that glowed once would never be able to glow again, even
	# after being removed and re-added (that was the actual bug).
	effectNode.effectFinished.connect(_on_effect_finished.bind(id))

func _getReactionPartForEffect() -> Node:
	#expand here
	return reactionData.getReactionPart("Na") 

func _getNewReactionPartsNames(data:Dictionary) -> Array:
	var possibleNewReactionParts = _getReactionPartsNotInReactionNames(data)
	return _getReactionPartsWithAmountGreater0(data, possibleNewReactionParts)

func _getReactionPartsNotInReactionNames(data:Dictionary) -> Array:
	var newReactionParts:Array = []
	for element in data.keys():
		if(element.begins_with("amount_of_")):
			element = element.substr(10)
			if(not reactionData.isChemicalPartOfReaction(element) and not reactionData.isChemicalPartOfLastRemoved(element)):
				newReactionParts.append(element)
	reactionData.lastRemovedCheckedNowSetToNull()
	return newReactionParts

func _getReactionPartsWithAmountGreater0(data: Dictionary, possibleNewReactionParts:Array) -> Array:
	var reactionPartsNames = []
	for elementName in possibleNewReactionParts:
		if(data.get("amount_of_"+elementName, 0.0) > DataSynchronizer.EXISTANCE_TRESHHOLD_IN_MOL):
			reactionPartsNames.append(elementName)
			print("reactionHandler: found new reaction part: ", elementName)
	return reactionPartsNames

func intantiateReactionParts(newReactionPartsNames:Array) -> void:
	for element in newReactionPartsNames:
		var newReactionPart = DataSynchronizer.instantiate(world, element)
		if(newReactionPart==null):
			push_error("ReactionHandler: tried to initialize but failed: "+ element)
		else:
			setPositionOfInstantiatedPart(newReactionPart)
			addReactionPart(newReactionPart.find_child("reactionPart"))
			

func setPositionOfInstantiatedPart(reactionPartNode: Node) -> void:
	reactionPartNode.global_transform.origin = reactionData.getReactingPosition()
	


func _on_reactionPartDepleted(reactionPart: ReactionPart) -> void:
	print("nwo removing and deleting reactionPart: " + reactionPart.getChemicalName())
	reactionData.queueReactionPartToRemove(reactionPart)
	_deleteReactionPart(reactionPart)

func _deleteReactionPart(reactionPart: ReactionPart) -> void:
	reactionPart.get_parent().queue_free()

func addReactionPart(part: ReactionPart) -> void:
	var reactionBefore = reactionData.getWhatReaction()
	reactionData.addReactionPart(part)
	if(reactionData.getWhatReaction() != reactionBefore):
		serverHandler.resetReactionInitialized()
		simulationData = []

func queueReactionPartToRemove(part: ReactionPart) -> void:
	reactionData.queueReactionPartToRemove(part)
