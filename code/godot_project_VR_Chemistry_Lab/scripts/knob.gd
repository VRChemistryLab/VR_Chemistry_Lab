extends RigidBody3D

# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	self.rotation_degrees.x = $InteractableHandle.rotation_degrees.x
