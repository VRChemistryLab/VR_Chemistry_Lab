@tool 
extends XRToolsPickable

@onready var snapzone_testtube = $snapzone_testtube

func _on_body_entered(body: Node) -> void: 
	if (body.is_in_group("dontCollideWithStandingCylinder")):
		self.add_collision_exception_with(body)

#disable testtube snap zone when cap is on the cylinder
func _on_snapzone_cap_has_picked_up(_what: Variant) -> void: 
	snapzone_testtube.enabled = false

#reenable testtube snap zone when cap is not on the cylinder
func _on_snapzone_cap_has_dropped() -> void:
	snapzone_testtube.enabled = true
