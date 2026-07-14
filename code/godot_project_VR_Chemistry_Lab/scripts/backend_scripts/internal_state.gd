extends Node
class_name InternalState
signal reactionPartDepleted(reactionPart)
var isConnectedToDataSynchronizerAndPartOfReaction: bool = false
var reactionPart: ReactionPart
var isPrecipitation: bool
var CHEMICAL_NAME: String 
var temperature: float : get=getTemperature, set=_setNewTemperature
const ROOM_TEMPERATURE_IN_KELVIN: float = 294 
var currentAmountInMol: float = 0: get = getCurrentAmountInMol, set = setCurrentAmountInMol
var shader: ShaderMaterial
var material : StandardMaterial3D
var myMeshNode

func _ready() -> void:
	reactionPart = self.get_parent()
	isPrecipitation = reactionPart.get_parent().is_in_group("precipitation")
	myMeshNode = reactionPart.get_parent().find_child("MeshInstance3D")
	temperature = ROOM_TEMPERATURE_IN_KELVIN
	CHEMICAL_NAME = reactionPart.getChemicalName()
	_setShader()
	# SCALING_FACTOR / _deriveScalingFactorFromInitialAmount fallen weg:
	# die Skalierung braucht keine Kalibrierung mehr, siehe _scaleMeshTo.

func _setShader() -> void:
	if myMeshNode == null or myMeshNode.mesh == null:
		push_error("reactionPart: "+CHEMICAL_NAME+" has no MeshInstance3D")
		return
	if is_instance_of(myMeshNode.mesh, ArrayMesh): 
		return
	var originalMaterial = myMeshNode.mesh.material
	if originalMaterial != null:
		if (originalMaterial is ShaderMaterial):
			shader = originalMaterial.duplicate(true) as ShaderMaterial
			myMeshNode.mesh.material = shader
		elif (originalMaterial is StandardMaterial3D):
			material = originalMaterial.duplicate(true) as StandardMaterial3D
			myMeshNode.mesh.material = material
	else:
		push_error("reactionPart: "+CHEMICAL_NAME+" has no ShaderMaterial")

func connectToDataSynchronizer() -> void:
	if(!isConnectedToDataSynchronizerAndPartOfReaction):
		isConnectedToDataSynchronizerAndPartOfReaction = true
		DataSynchronizer.connect("dataChanged", Callable(self, "_on_data_changed"))
		reactionPartDepleted.connect(Callable(DataSynchronizer.reactionGroupManager, "onPartDepleted"))

func disconnectFromDataSynchronizer() -> void:
	if(isConnectedToDataSynchronizerAndPartOfReaction):
		isConnectedToDataSynchronizerAndPartOfReaction = false
		DataSynchronizer.disconnect("dataChanged", Callable(self, "_on_data_changed"))
		DataSynchronizer.reactionGroupManager.onPartLeftReaction(reactionPart)
		reactionPartDepleted.disconnect(Callable(DataSynchronizer.reactionGroupManager, "onPartDepleted"))

func getTemperature() -> float:
	return temperature

func addToTemperature(howMuchToAddToTemperature: float):
	_setNewTemperature(temperature+howMuchToAddToTemperature)

func _setNewTemperature(newTemperature:float) -> void:
	temperature = newTemperature

func getCurrentAmountInMol() -> float:
	return currentAmountInMol

func setCurrentAmountInMol(newAmount:float) -> void:
	currentAmountInMol = newAmount
	if(isPrecipitation):
		_scaleMeshTo(newAmount)
	if(newAmount<=DataSynchronizer.EXISTANCE_TRESHHOLD_IN_MOL):
		emit_signal("reactionPartDepleted", self.reactionPart)

func _scaleMeshTo(amountInMol: float) -> void:
	var linearScale = pow(max(amountInMol, 0.0), 1.0/3.0) #bc volume
	self.myMeshNode.scale = Vector3(linearScale, linearScale, linearScale)

func equals(otherState: InternalState) -> bool:
	if(self.temperature != otherState.getTemperature()):
		return false
	elif(self.currentAmountInMol != otherState.getCurrentAmountInMol()):
		return false
	return true

func _on_data_changed(data:Dictionary) -> void:
	if(isAffectedByData(data)):
		setEffectsFromData(data)

func isAffectedByData(data: Dictionary) -> bool:
	assert(data.has("reactionIds"))
	var reactionIds: Dictionary = data.get("reactionIds")
	if not reactionIds.has(CHEMICAL_NAME):
		return false
	if int(reactionIds.get(CHEMICAL_NAME)) != reactionPart.get_instance_id():
		return false
	# Being physically part of a reaction group (=> listed in reactionIds)
	# does not mean the active engine/mechanism actually tracks this
	# chemical (e.g. a bystander species not consumed/produced by the
	# reaction currently running for this group, like NaBr sitting inert
	# next to an Na+Cl2 reaction). Only react to data that actually reports
	# an amount for this chemical - otherwise leave it untouched.
	return data.has(_getAmountOfSelfInSyntax())

func _getAmountOfSelfInSyntax() -> String:
	return "amount_of_" + reactionPart.getChemicalName()

func setEffectsFromData(data: Dictionary) -> void:
	if data.has("temperature"):
		_setNewTemperature(data.get("temperature"))
	# Defensive default on top of the isAffectedByData guard above - if this
	# chemical's amount isn't reported this step, keep its current amount
	# instead of crashing (float can't hold null) or silently zeroing it out.
	setCurrentAmountInMol(data.get(_getAmountOfSelfInSyntax(), currentAmountInMol))
