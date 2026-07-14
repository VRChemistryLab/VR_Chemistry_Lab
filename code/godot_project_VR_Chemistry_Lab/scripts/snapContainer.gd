@tool
class_name SnapContainer
extends XRToolsPickable

var contents: Array = []
var parent_containers: Array = []   # containers I'm currently snapped into (can be more than one level deep)

func _on_snap_zone_has_picked_up(what: Variant) -> void:
	add_collision_exception_with(what)
	contents.append(what)
	
	_removeNullEntriesFromList(parent_containers)
	# propagate the exception up through my own parent chain (Stand etc.)
	for ancestor in parent_containers:
		ancestor.add_collision_exception_with(what)

	# if what already has nested contents, except those too,
	# against me AND against my ancestors
	if what.has_method("get_all_nested_contents"):
		for nested in what.get_all_nested_contents():
			add_collision_exception_with(nested)
			for ancestor in parent_containers:
				ancestor.add_collision_exception_with(nested)

	# Tell "what" who its containers are now, so if IT picks something up later,
	# it knows to propagate further up too
	if what.has_method("add_parent_container"):
		what.add_parent_container(self)
		for ancestor in parent_containers:
			what.add_parent_container(ancestor)


func _on_snap_zone_has_dropped(what: Variant) -> void:
	contents.erase(what)

	await get_tree().physics_frame
	await get_tree().physics_frame

	if is_instance_valid(what):
		remove_collision_exception_with(what)
		_removeNullEntriesFromList(parent_containers)
		for ancestor in parent_containers:
			ancestor.remove_collision_exception_with(what)
		if what.has_method("clear_parent_containers"):
			what.clear_parent_containers()


func add_parent_container(container: Node) -> void:
	if container not in parent_containers:
		parent_containers.append(container)


func clear_parent_containers() -> void:
	parent_containers.clear()


func get_all_nested_contents() -> Array:
	_removeNullEntriesFromList(contents) 
	var all := contents.duplicate()
	for c in contents:
		if c.has_method("get_all_nested_contents"):
			all += c.get_all_nested_contents()
	return all

func _removeNullEntriesFromList(list: Array):
	list = list.filter(func(c): return is_instance_valid(c)) #removes freed items from the array
