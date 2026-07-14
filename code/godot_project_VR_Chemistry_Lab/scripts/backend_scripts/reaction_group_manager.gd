extends Node
# Dynamically resolves which ReactionInstance a ReactionPart currently belongs to.

var partToGroupId: Dictionary = {}       # ReactionPart -> String (group_id)
var groupIdToInstance: Dictionary = {}   # group_id -> ReactionInstance-Root-Node
var _nextGroupId: int = 0

# ── Entry points ──────────────────────────────────────────────────────────

# two Parts collide physicly (reaction_part.gd: _on_area_3d_area_entered)
func onPartsCollided(partA: ReactionPart, partB: ReactionPart) -> void:
	if partA == partB:
		return

	var groupA = partToGroupId.get(partA, null)
	var groupB = partToGroupId.get(partB, null)

	if groupA == null and groupB == null:
		var newGroup = _createNewGroup()
		_assignPartToGroup(partA, newGroup)
		_assignPartToGroup(partB, newGroup)
	elif groupA == null:
		_assignPartToGroup(partA, groupB)
	elif groupB == null:
		_assignPartToGroup(partB, groupA)
	elif groupA != groupB:
		_mergeGroups(groupA, groupB)

# A part appears in the reaction without a collision partner, e.g. when
# heating without contact with another chemical (reaction_part.gd: setIsInFlame)
# or when initially placed (reaction_part.gd: addSelfToReaction)
func onPartAppeared(part: ReactionPart) -> void:
	if partToGroupId.has(part):
		return
	var newGroup = _createNewGroup()
	_assignPartToGroup(part, newGroup)

# Part physically separates from the reaction but continues to exist
# (internal_state.gd: disconnectFromDataSynchronizer, triggered by area_exited)
func onPartLeftReaction(part: ReactionPart) -> void:
	var groupId = partToGroupId.get(part, null)
	if groupId == null:
		return
	partToGroupId.erase(part)
	
	var reactionHandler = _getReactionHandler(groupId)
	if reactionHandler != null:
		reactionHandler.queueReactionPartToRemove(part)
	
	_cleanupGroupIfEmpty(groupId)

# Part is consumed/depleted and is deleted
# (internal_state.gd: reactionPartDepleted signal)
func onPartDepleted(part: ReactionPart) -> void:
	var groupId = partToGroupId.get(part, null)
	partToGroupId.erase(part)
	
	if groupId == null:
		if is_instance_valid(part) and part.get_parent() != null:
			part.get_parent().queue_free()
		return
	
	var reactionHandler = _getReactionHandler(groupId)
	if reactionHandler != null:
		reactionHandler._on_reactionPartDepleted(part)
	
	_cleanupGroupIfEmpty(groupId)

# ── Lookups, used by reaction_part.gd for setJustStartedHeating/setJustStoppedHeating ──

func getInstanceForPart(part: ReactionPart) -> Node:
	var groupId = partToGroupId.get(part, null)
	if groupId == null:
		return null
	return groupIdToInstance.get(groupId, null)

func getReactionHandlerForPart(part: ReactionPart) -> Node:
	return getInstanceForPart(part)

# ── internal ───────────────────────────────────────────────────────────────────

func _createNewGroup() -> String:
	_nextGroupId += 1
	var groupId = "reaction_%d" % _nextGroupId
	groupIdToInstance[groupId] = DataSynchronizer.createReactionInstance(groupId)
	return groupId

func _assignPartToGroup(part: ReactionPart, groupId: String) -> void:
	partToGroupId[part] = groupId
	var reactionHandler = _getReactionHandler(groupId)
	if reactionHandler != null:
		reactionHandler.addReactionPart(part)

func _mergeGroups(groupA: String, groupB: String) -> void:
	# Move all parts from group B to group A, then destroy group B.
	var reactionHandlerA = _getReactionHandler(groupA)
	
	for part in partToGroupId.keys():
		if partToGroupId[part] == groupB:
			partToGroupId[part] = groupA
			if reactionHandlerA != null:
				reactionHandlerA.addReactionPart(part)
	
	DataSynchronizer.removeReactionInstance(groupB)
	groupIdToInstance.erase(groupB)

func _getReactionHandler(groupId: String) -> Node:
	var instance = groupIdToInstance.get(groupId, null)
	if instance == null or not is_instance_valid(instance):
		return null
	return instance

func _cleanupGroupIfEmpty(groupId: String) -> void:
	if _groupIsEmpty(groupId):
		DataSynchronizer.removeReactionInstance(groupId)
		groupIdToInstance.erase(groupId)

func _groupIsEmpty(groupId: String) -> bool:
	for existingGroupId in partToGroupId.values():
		if existingGroupId == groupId:
			return false
	return true

# ── Debug ─────────────────────────────────────────────────────────

func getActiveGroupCount() -> int:
	return groupIdToInstance.size()

func getGroupIdForPart(part: ReactionPart) -> String:
	return partToGroupId.get(part, "")
