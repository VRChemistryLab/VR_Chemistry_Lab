@tool
extends XRToolsPickable

@onready var snapZone = $snapzone_chemical

@onready var anim = $AnimationPlayer

var pickedByLeft = false

func action():
	snapZone.enabled = true
	if (pickedByLeft):
		anim.play("left_closed")
	else:
		anim.play("right_closed")

func action_release():
	snapZone.enabled = false
	snapZone.drop_object()
	if (pickedByLeft):
		anim.play("left_open")
	else:
		anim.play("right_open")
	
	# changing which animation gets played depending on which hand picked up
	# adjusting snapzone to match 
	if self.get_picked_up_by().get_parent().name == "LeftHand":
		pickedByLeft = true
		snapZone.position.x = -0.005
	if self.get_picked_up_by().get_parent().name == "RightHand":
		pickedByLeft = false
		snapZone.position.x = 0.005


func _on_dropped(_pickable: Variant) -> void:
	snapZone.enabled = false
	snapZone.drop_object()
	anim.play("RESET")
