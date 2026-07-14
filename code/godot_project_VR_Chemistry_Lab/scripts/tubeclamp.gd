@tool
extends XRToolsPickable

@onready var snapZone : XRToolsSnapZone = $snapzoneTestTube
# for delay/cooldown after dropping a testtube
@onready var snapDropTimer :Timer = $timer_snapzonedrop

@onready var anim : AnimationPlayer = $AnimationPlayer

var hasTube : bool = false

#picking up testtube
func action():
	#triggering action when hasTube drops the tube
	if (hasTube):
		hasTube = false
		snapZone.drop_object()
		snapDropTimer.start(1.0)
	#triggering while empty enables snapZone for tube
	else:
		snapZone.enabled = true
		anim.play("open")
	

func action_release():
	snapDropTimer.stop()
	snapZone.enabled = false
	#letting go without testtube closes the clamp
	if(!hasTube):
		anim.play("closed")



func _on_picked_up(_pickable: Variant) -> void:
	#rotating tube snapZone depending on which hand picked up
	if self.get_picked_up_by().get_parent().name == "LeftHand":
		snapZone.rotation_degrees.x = 0
	if self.get_picked_up_by().get_parent().name == "RightHand":
		snapZone.rotation_degrees.x = 180


#dropping the tweezer lets go of the attached tube
func _on_dropped(_pickable: Variant) -> void:
	snapZone.enabled = false
	snapZone.drop_object()
	anim.play("RESET")

func _on_snapzone_test_tube_has_picked_up(_what: Variant) -> void:
	hasTube = true

#reenable snapzone after dropping object if trigger is held
func _on_timer_snapzonedrop_timeout() -> void:
	snapZone.enabled = true
