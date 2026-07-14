@tool
extends XRToolsSnapZone

signal who_has_dropped

func _on_has_dropped() -> void:
	emit_signal("who_has_dropped", self)
