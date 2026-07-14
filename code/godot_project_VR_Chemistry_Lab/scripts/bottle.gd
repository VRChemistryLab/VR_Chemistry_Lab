@tool
extends XRToolsPickable


@onready var spawner_chemical = $spawner_chemical

func _on_body_entered(body: Node) -> void:
	if (body.is_in_group("dontCollideWithBottle")):
		self.add_collision_exception_with(body)
		

#disable picking up chemicals when cap is on the bottle
func _on_snapzone_cap_has_picked_up(_what: Variant) -> void:
	var chemical = spawner_chemical.getCurrentInSpawn()
	chemical.enabled = false

#reenable picking up chemicals when cap is not on the bottle
func _on_snapzone_cap_has_dropped() -> void:
	var chemical = spawner_chemical.getCurrentInSpawn()
	chemical.enabled = true
