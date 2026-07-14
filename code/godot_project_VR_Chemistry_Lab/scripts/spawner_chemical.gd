extends Node3D

@export var spawnedObject : PackedScene
var currentInSpawn

@export var maxInstances : int = 5

var index : int = 0

var instanceArray : Array[Node]

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	spawn()


func spawn():
	# delete first object if over max
	if (instanceArray.size() > maxInstances):
		var overflow = instanceArray.pop_front()
		despawn(overflow)

	# instantiate new
	var instance = spawnedObject.instantiate()
	instance.freeze = true
	
	# for the bottle to use
	currentInSpawn = instance
	
	# adding instance to instance array
	instanceArray.push_back(instance)
	
	# indexing objects for easier use and adding to scene
	instance.name = instance.name + str(index) 
	index += 1
	add_child(instance)
	

func despawn(which :Node3D):
	var reactionPart = which.find_child("reactionPart")
	if reactionPart != null:
		DataSynchronizer.reactionGroupManager.onPartLeftReaction(reactionPart)
	which.position.y = 2.6
	await get_tree().create_timer(1.0).timeout
	which.queue_free()
	#print(which.name, "has been despawned",currentInstances)

func getCurrentInSpawn():
	return currentInSpawn
