extends Node
class_name ReactionPart

@export var CHEMICAL_NAME: String: get=getChemicalName
@export var AMOUNT_IN_MOL: float = 1
var isPartOfReaction: bool = false: get=getIsPartOfReaction, set=setIsPartOfReaction
var isInFlame: bool = false: set=setIsInFlame, get=getIsInFlame

func _ready() -> void:
	getState().setCurrentAmountInMol(AMOUNT_IN_MOL)
	_connectSignals()

func _connectSignals() -> void:
	var area = get_parent().get_node("Area3D")
	area.connect("area_entered", Callable(self, "_on_area_3d_area_entered"))
	area.connect("area_exited", Callable(self, "_on_area_3d_area_exited"))

func _process(_delta: float) -> void:
	if(DataSynchronizer.printTemperatureEveryProcess):
		print("Temp of "+CHEMICAL_NAME+" is: "+str(getState().getTemperature()))

func getState() -> InternalState:
	return $InternalState

func getChemicalName() -> String:
	return CHEMICAL_NAME

func addSelfToReaction() -> void:
	DataSynchronizer.reactionGroupManager.onPartAppeared(self)

func getIsPartOfReaction() -> bool:
	return isPartOfReaction

func setIsPartOfReaction(isIt:bool) -> void:
	isPartOfReaction = isIt
	if(isPartOfReaction):
		getState().connectToDataSynchronizer()
	else:
		getState().disconnectFromDataSynchronizer()

func setIsInFlame(isSupposedToBeInFlameNow:bool) -> void:
	print("reactionPart: setting in flame to: " + str(isSupposedToBeInFlameNow))
	if(isSupposedToBeInFlameNow and !isInFlame):
		isInFlame = isSupposedToBeInFlameNow
		DataSynchronizer.reactionGroupManager.onPartAppeared(self)
		var reactionHandler = DataSynchronizer.reactionGroupManager.getReactionHandlerForPart(self)
		if reactionHandler != null:
			reactionHandler.setJustStartedHeating(true)
		setIsPartOfReaction(true)
	elif(!isSupposedToBeInFlameNow and isInFlame):
		isInFlame = isSupposedToBeInFlameNow
		var reactionHandler = DataSynchronizer.reactionGroupManager.getReactionHandlerForPart(self)
		if reactionHandler != null:
			reactionHandler.setJustStoppedHeating(true)
		setIsPartOfReaction(false)

func getIsInFlame() -> bool:
	return isInFlame

func _on_area_3d_area_entered(area: Area3D) -> void:
	if(_collidingWithOtherReactionPart(area)):
		var otherPart: ReactionPart = area.get_parent().get_node("reactionPart")
		getState().connectToDataSynchronizer()
		DataSynchronizer.reactionGroupManager.onPartsCollided(self, otherPart)
	elif(_collidingWithFlame(area)):
		setIsInFlame(true)
	else:
		print("reactionPart "+CHEMICAL_NAME+" collided with: "+str(area))

func _collidingWithOtherReactionPart(area: Area3D) -> bool:
	if( area.get_parent().has_node("reactionPart") ):
		return area.get_parent().get_node("reactionPart").getChemicalName() != CHEMICAL_NAME
	return false

func _collidingWithFlame(area: Area3D) -> bool:
	return area.is_in_group("flame")

func _on_area_3d_area_exited(area: Area3D) -> void:
	if(_collidingWithOtherReactionPart(area)):
		getState().disconnectFromDataSynchronizer()
	elif(_collidingWithFlame(area)):
		setIsInFlame(false)
	else:
		print("reactionPart "+CHEMICAL_NAME+" stopped coliding with: "+str(area))
