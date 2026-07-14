extends XROrigin3D

@onready var left : XRController3D = $LeftHand
@onready var right : XRController3D = $RightHand

var maxHeight : float = 0.8

var rightstickmoved : bool = false
var leftstickmoved : bool = false

func _process(_delta: float) -> void:
	if(rightstickmoved):
		adjustCamHeight()
	if(leftstickmoved):
		adjustCamAngle()

func _on_right_hand_input_vector_2_changed(_name: String, value: Vector2) -> void:
	if(value.y == 0):
		rightstickmoved = false
	else:
		rightstickmoved = true


func _on_left_hand_input_vector_2_changed(_name: String, value: Vector2) -> void:
	if(value.y == 0):
		leftstickmoved = false
	else:
		leftstickmoved = true


func adjustCamHeight ():
	var newHeight = self.position.y + right.get_vector2("primary").y / 100
	if (abs(newHeight) < maxHeight):
		self.position.y = newHeight

func adjustCamAngle():
	self.rotation.y = self.rotation.y - left.get_vector2("primary").x / 100
