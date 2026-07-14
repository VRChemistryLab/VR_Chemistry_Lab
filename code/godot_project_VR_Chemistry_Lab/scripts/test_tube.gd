@tool
extends SnapContainer

func _on_body_entered(body: Node) -> void:
	if (body.is_in_group("dontCollideWithTestTube")):
		self.add_collision_exception_with(body)
