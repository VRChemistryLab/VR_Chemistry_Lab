@tool
extends XRToolsPickable

var ceiling
var lights
var material

var lightOn : bool = true

@onready var anim = $AnimationPlayer


# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	super._ready()
	ceiling = get_node(^"/root/main/room/ceiling")
	lights = ceiling.find_child("lights")
	material = ceiling.find_child("mesh_ceiling").mesh.material


func action():
	anim.play("press")
	if(!lightOn):
		turnLightOn();
	elif (lightOn):
		turnLightOff()

func action_release():
	anim.play("release")


func turnLightOn():
	lightOn = true
	lights.visible = true
	material.set_emission_energy_multiplier(3.0)

func turnLightOff():
	lightOn = false
	lights.visible = false
	material.set_emission_energy_multiplier(0.0)
	
func _on_picked_up(_pickable: Variant) -> void:
	lightOn = lights.is_visible_in_tree()


func _on_dropped(_pickable: Variant) -> void:
	anim.play("RESET")
