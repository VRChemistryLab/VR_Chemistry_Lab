extends AudioStreamPlayer3D

@onready var parent = self.get_parent()
var audioThreshhold = 0.2

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	parent.connect("body_entered", Callable(self, "on_body_entered"))

func on_body_entered(_body: Node):
	playCollisionSound();

func playCollisionSound():
	if abs(parent.linear_velocity.x) > audioThreshhold or abs(parent.linear_velocity.y) > audioThreshhold or abs(parent.linear_velocity.z) > audioThreshhold:
		self.play();
