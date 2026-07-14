extends Node3D
var time = 0
var hasHappened = false
var trans: Transform3D
# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	#$chemicals/Na/reactionPart/InternalState._setNewTemperature(400)
	#trans = $Na.transform
	#$Na/reactionPart/InternalState.setCurrentAmountInMol(1)
	#DataSynchronizer.reactionHandler.addReactionPart($Br2/reactionPart)
	#DataSynchronizer.reactionHandler.addReactionPart($Na/reactionPart)
	#$Na/reactionPart.setIsInFlame(true)
	#$Br2/reactionPart.setIsInFlame(true)
	var na = $chemicals/Na/reactionPart
	na.isInFlame = true
	var cl = $chemicals/standingcylinder_cl2/Cl2/reactionPart
	#DataSynchronizer.reactionGroupManager.onPartsCollided(na, cl)
	var na2 = $chemicals/Na2/reactionPart
	var br = $chemicals/standingcylinder_br2/Br2/reactionPart
	#DataSynchronizer.reactionGroupManager.onPartsCollided(na2, br)


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(_delta: float) -> void:
	
	"""
	time+=_delta
	if(time > 2):
		time = 0
		if(not hasHappened):
			hasHappened = true
			#$Na/reactionPart.setIsInFlame(true)
			$Na.transform = Transform3D(Vector3(1000.2,1000.3,1000.3), Vector3(1000.2,1000.3,1000.3), Vector3(1000.2,1000.3,1000.3), Vector3(1000.2,1000.3,1000.3))
		else:
			hasHappened = false
			#$Na/reactionPart.setIsInFlame(false)
			$Na.transform = trans
	"""


func _on_timer_timeout() -> void:
	pass#$Na/reactionPart.setIsInFlame(false)
	
