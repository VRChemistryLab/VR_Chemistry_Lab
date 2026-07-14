@tool
extends XRToolsPickable

var inSpawn : bool = true

func _on_picked_up(_pickable: Variant) -> void:
	# grabbing the object that was on the spawn
	# sets flag to false and spawns new
	if(inSpawn):
		inSpawn = false
		get_parent().spawn()
		self.top_level = true
