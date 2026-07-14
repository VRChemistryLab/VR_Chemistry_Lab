extends Node3D

var inSpawn : bool = true
@onready var parent = self.get_parent()

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	parent.connect("picked_up",Callable(self, "on_picked_up"))

func on_picked_up(_pickable: Variant):
	# grabbing the object that was on the spawn
	# sets flag to false and spawns new 
	# by calling the spawn() method in the spawner (parent)
	if(inSpawn):
		inSpawn = false
		parent.get_parent().spawn()
