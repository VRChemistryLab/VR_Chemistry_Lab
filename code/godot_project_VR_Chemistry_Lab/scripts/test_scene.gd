extends Node3D

var timer: float = 1
# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	pass

# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	timer-=delta
	if(timer<=0 and timer >-1000):
		initializeTestReaktionParts()
		timer = -1000000

func initializeTestReaktionParts() -> void:
	#$TestNa/reaktionPart.setIsPartOfReaktion(true)
	#$TestBr2/reaktionPart.setIsPartOfReaktion(true)
	pass
