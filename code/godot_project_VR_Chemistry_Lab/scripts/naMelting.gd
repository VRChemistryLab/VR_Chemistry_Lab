# meltable_mesh.gd
extends MeshInstance3D

@export var melt_start: float = 400.0
@export var melt_end: float = 600.0

@onready var reaction_part: Node = get_node("../reactionPart")
@onready var lastTemp: float = reaction_part.getState().get("temperature")


func _process(_delta: float) -> void:
	var newTemp = reaction_part.getState().get("temperature")
	if(newTemp!=lastTemp):
		_update_melt(newTemp)
		lastTemp = newTemp

func _update_melt(temperature: float) -> void:
	var t:float = clamp((temperature - melt_start) / (melt_end - melt_start), 0.0, 1.0)
	self.set_blend_shape_value(0, 1-t)  # Index, Wert (0.0–1.0)
	var m2: ArrayMesh = mesh as ArrayMesh 
