extends Node3D

@export var spawnedObject : PackedScene

@export var maxInstances : int = 5

var index : int = 0

@onready var despawnAudio : AudioStreamPlayer3D = $"../../audio_despawn"

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
	
	# adding instance to instance array
	instanceArray.push_back(instance)
	
	# indexing objects for easier use and adding to scene
	instance.name = instance.name + str(index) 
	index += 1
	add_child(instance)
	

func despawn(which :Node3D):
	var snapzoneChildren = which.find_children("*","XRToolsSnapZone")
	for snapzone in snapzoneChildren:
		snapzone.drop_object()
	despawnAudio.play()
	which.queue_free()
	

func _on_area_3d_body_entered(body: Node3D) -> void:
	if (body.is_in_group("tool") and !body.find_child("spawn_activator").inSpawn):
		var bodyParent = body.get_parent()
		var indexToDespawn = bodyParent.instanceArray.find(body)
		var toDespawn = bodyParent.instanceArray.pop_at(indexToDespawn)
		despawn(toDespawn)
	
