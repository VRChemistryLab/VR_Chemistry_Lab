@tool
extends XRToolsPickable

@onready var knob = $bunsenburnerknob
@onready var knobClickAudio = $audio_knobClick

@onready var flame = $particle_flame
@onready var flameCollider = $area_flame/collider_flame
@onready var flameLight = $light_flame
@onready var flameAudio = $audio_bunsenburnerFlame


var isTurning : bool = false
var inSpawn : bool = true

func _process(_delta: float) -> void:
	if(isTurning):
		flameActivation()
		


func _on_bunsenburnerknob_is_turning(started: bool) -> void:
	isTurning = started

func flameActivation():
	if(knob.rotation_degrees.z < -60):
		flame.emitting = true
		flameCollider.disabled = false
		flameLight.visible = true
		flameAudio.play()
		knobClickAudio.play()
	else:
		flame.emitting = false
		flameCollider.disabled = true
		flameLight.visible = false
		flameAudio.stop()
