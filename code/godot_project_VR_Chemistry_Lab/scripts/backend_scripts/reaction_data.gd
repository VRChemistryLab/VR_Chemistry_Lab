extends Node

var whatReaction:String = "": get=getWhatReaction #unique Identifier for reacions:list of produkts
var reactingPosition: Vector3 
var reactionParts: Dictionary = {}
var reactionPartsObjectIDs: Dictionary = {}: get=getReactionIDs
var reactionPartsToRemove: Array = []
var lastChemicalsRemoved: Array = []

## Counts every time a reaction part is actually added to or removed from
## reactionParts - not how many parts currently exist, just how many times
## the set has changed. This is what reaction_handler.gd uses to tell "the
## glow effect finished on its own (composition unchanged)" apart from "Na
## was actually taken out and put back in (composition changed)", even when
## it's the exact same Na instance re-entering with the same object id.
var compositionVersion: int = 0: get=getCompositionVersion

func _process(_delta: float) -> void:
	_removeNullReactionParts()
	_removeReactionPartsQueuedToBeRemoved()
	if(DataSynchronizer.printReactionPartsInReaction):
		_printAllReactionParts()

func _removeNullReactionParts():
	for key in reactionParts.keys():
		if reactionParts[key] == null:
			reactionParts.erase(key)
			compositionVersion += 1

func _removeReactionPartsQueuedToBeRemoved() -> void:
	for part in reactionPartsToRemove:
		if part != null:
			_removeReactionPart(part)
			lastChemicalsRemoved.append(part.getChemicalName())
	reactionPartsToRemove = []


func queueReactionPartToRemove(part:ReactionPart) -> void:
	reactionPartsToRemove.append(part)

func _removeReactionPart(part: ReactionPart) -> void:
	var nameOfReactionPartToRemove = part.getChemicalName()
	reactionParts.erase(nameOfReactionPartToRemove)
	reactionPartsObjectIDs.erase((nameOfReactionPartToRemove))
	compositionVersion += 1
	_setReactionOrHeatingFromParts()
	_setPositionForReaction()

func addReactionPart(part: ReactionPart) -> void:
	var nameOfReactionPartToAdd = part.getChemicalName()
	reactionParts.set(part.getChemicalName(), part)
	reactionPartsObjectIDs.set(part.getChemicalName(), part.get_instance_id())
	compositionVersion += 1
	_setReactionOrHeatingFromParts()
	_setPositionForReaction()

func _setReactionOrHeatingFromParts() -> void:
	var reaction = _getReactionFromParts()
	if(reaction == ""):
		reaction = _getWhatHeatedFromParts()
	whatReaction = reaction
	

func _getReactionFromParts() -> String:
	var reaction : String = DataSynchronizer.reactionRegistry.findReactionByReactants(reactionParts)
	if reaction == "":
		reaction = _getAqueousReactionFromParts()
	return reaction

func _getAqueousReactionFromParts() -> String:
	var presentAqueousNames: Array = []
	for chemicalName in reactionParts.keys():
		if DataSynchronizer.reactionRegistry.aqueousReagents.has(chemicalName):
			presentAqueousNames.append(chemicalName)
	if presentAqueousNames.size() < 2:
		return ""
	presentAqueousNames.sort()
	# Prefix "Aqueous:" is what DataSynchronizer.reactionRegistry matches on
	# (isPrefix entry) to route to the "WebSocket Reaktoro" engine - see
	# DataSynchronizer.getEngineConnectionForReaction().
	return "Aqueous:" + "+".join(presentAqueousNames)

func _getWhatHeatedFromParts() -> String:
	for chemical in reactionParts.values():
		if chemical != null and chemical.getIsInFlame():
			return chemical.getChemicalName()
	return ""

func _setPositionForReaction() -> void:
	if(len(reactionParts)<=0):
		reactingPosition = Vector3.ZERO
	else:
		var newPosition= Vector3.ZERO
		for part in reactionParts:
			if(reactionParts.get(part) != null):
				var node = reactionParts.get(part)
				newPosition.x += node.global_transform.origin.x
				newPosition.y += node.global_transform.origin.y
				newPosition.z += node.global_transform.origin.z
		reactingPosition = newPosition*(1.0/len(reactionParts))

func getReactionTemperature() -> float:
	#not final
	var temperature:float = 0
	for part in reactionParts:
		if(reactionParts.get(part) != null):
			var temperatureOfPart = reactionParts.get(part).getState().getTemperature()
			if(temperatureOfPart > temperature):
				temperature = temperatureOfPart
	return temperature

func getReactionAmountInMol() -> Dictionary:
	var amountInMol: Dictionary = {}
	for part in reactionParts:
		if(reactionParts.get(part) != null):
			amountInMol[part] = reactionParts.get(part).getState().getCurrentAmountInMol()
	return amountInMol


func getWhatReaction() -> String:
	return whatReaction

func getReactionPart(identifier: String) -> ReactionPart:
	return reactionParts[identifier]

func isChemicalPartOfReaction(identifier: String) -> bool: 
	return reactionParts.has(identifier)

func isChemicalPartOfLastRemoved(identifier: String) -> bool: 
	return lastChemicalsRemoved.has(identifier)

func lastRemovedCheckedNowSetToNull() -> void:
	lastChemicalsRemoved = []

func reactionDetected() -> bool:
	return whatReaction!=""

func getReactingPosition() -> Vector3:
	return reactingPosition

func getReactionIDs() -> Dictionary:
	return reactionPartsObjectIDs

func getCompositionVersion() -> int:
	return compositionVersion

func _printAllReactionParts():
	if(not reactionDetected()):
		print("reactingData: no reactionParts in reaction yet.")
	else:
		var s = "ReactionData: all reactionParts in reaction: "
		for part in reactionParts:
			if(reactionParts.get(part) != null):
				s+= part + ", "
		print(s)
