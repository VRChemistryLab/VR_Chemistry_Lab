extends Node

var pathToChemicals := "res://objects/chemicals"
var allChemicals: Dictionary = {}

var hardcodedChemicals := {
	"NaBr": preload("res://objects/chemicals/NaBr.tscn"),
	"NaCl": preload("res://objects/chemicals/NaCl.tscn"),
	"NaI": preload("res://objects/chemicals/naI.tscn"),
}

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	addAllChemicalsToDictionary()

func addAllChemicalsToDictionary() -> void:
	var directory := DirAccess.open(pathToChemicals)
	if directory == null:
		push_error("Chemicals directory not found: " + pathToChemicals)
		return
		
	directory.list_dir_begin()
	var fileName := directory.get_next()

	while fileName != "":
		if not directory.current_is_dir() and fileName.ends_with(".tscn"):
			var chemicalName := fileName.replace(".tscn", "")
			var scenePath := pathToChemicals + "/" + fileName
			allChemicals[chemicalName] = scenePath
		fileName = directory.get_next()
	directory.list_dir_end()

func instantiate(parent: Node, element: String) -> Node:
	if(element not in allChemicals):
		push_error("ElementInstantiator: element does not exist and can therefore not be initialized: ", element)
		return
	var scenePath: String = allChemicals[element]
	var elementScene: PackedScene = load(scenePath)
	if elementScene == null:
		push_error("Could not load scene: " + scenePath)
		return

	var instance = elementScene.instantiate()
	parent.add_child(instance)
	
	return instance
