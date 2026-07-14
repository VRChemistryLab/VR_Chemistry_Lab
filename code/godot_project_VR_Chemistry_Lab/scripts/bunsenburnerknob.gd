extends Node3D

@onready var handler : XRToolsInteractableHandle = $InteractableHandle
var handlerOriginalTransform : Transform3D
var turning : bool
var handlerRotationStart : float= 0
var knobRotationStart : float = 0
var turnby : float

var updatedKnobRotation : float

signal isTurning(started: bool)

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	handlerOriginalTransform = handler.transform


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(_delta: float) -> void:
	turningKnob()
	if not turning:
		handler.transform = handlerOriginalTransform

func _on_interactable_handle_picked_up(_pickable: Variant) -> void:
	handlerRotationStart = handler.rotation_degrees.z
	turning = true
	emit_signal("isTurning", true)

func _on_interactable_handle_dropped(_pickable: Variant) -> void:
	turning = false
	emit_signal("isTurning", false)
	
func turningKnob():
	turnby = handler.rotation_degrees.z - handlerRotationStart
	updatedKnobRotation = knobRotationStart + turnby
	if(turning):
		rotatewithinboundary()
		self.rotation_degrees.z = updatedKnobRotation

func rotatewithinboundary():
	if (updatedKnobRotation > 0):
		updatedKnobRotation = 0
	if (updatedKnobRotation < -90):
		updatedKnobRotation = -90
