extends Node
var registeredHandlers: Dictionary = {}  # reactionInstanceId(String) -> serverHandler(Node)
func registerServerHandler(serverHandler: Node, reactionInstanceId: String) -> void:
	if reactionInstanceId == "":
		push_error("MessageRouter: registerServerHandler with empty reactionInstanceId")
		return
	registeredHandlers[reactionInstanceId] = serverHandler
func unregisterServerHandler(reactionInstanceId: String) -> void:
	registeredHandlers.erase(reactionInstanceId)
func onMessageFromServer(text: String) -> void:
	var reactionInstanceId = _extractReactionInstanceId(text)
	if reactionInstanceId == "":
		print("MessageRouter: message without reactionInstanceId, dropping: ", text)
		return
	if not registeredHandlers.has(reactionInstanceId):
		return
	var serverHandler: Node = registeredHandlers[reactionInstanceId]
	if not is_instance_valid(serverHandler):
		registeredHandlers.erase(reactionInstanceId)
		return
	serverHandler.onMessageFromServer(text)
func _extractReactionInstanceId(text: String) -> String:
	var parsed = JSON.parse_string(text)
	if parsed == null or typeof(parsed) != TYPE_DICTIONARY:
		return ""
	if parsed.has("reactionInstanceId"):
		return str(parsed.get("reactionInstanceId", ""))
	var dataBlockList = parsed.get("dataBlockList", [])
	if typeof(dataBlockList) == TYPE_ARRAY and dataBlockList.size() > 0:
		var firstEntry = dataBlockList[0]
		if typeof(firstEntry) == TYPE_DICTIONARY and firstEntry.has("reactionInstanceId"):
			return str(firstEntry.get("reactionInstanceId", ""))
	return ""
