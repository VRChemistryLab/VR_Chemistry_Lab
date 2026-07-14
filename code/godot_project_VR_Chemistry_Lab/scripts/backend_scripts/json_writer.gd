extends Node
func _getJsonFromData(whatReaction: String, reactionIds: Dictionary, targetTime: float, methodName: String, reactionInstanceId: String, temperature: float = -1, amountInMol = null) -> String:
	var data = {
		"whatReaction"       : whatReaction,
		"reactionIds"        : reactionIds,
		"targetTime"         : targetTime,
		"methodName"         : methodName,
		"temperature"        : temperature,
		"reactionInstanceId" : reactionInstanceId,
		"amountInMol"        : amountInMol,
	}
	return JSON.stringify(data)
func getJsonFromDataForInit(whatReaction: String, reactionIds: Dictionary, targetTime: float, temperature: float, reactionInstanceId: String, amountInMol) -> String:
	return _getJsonFromData(whatReaction, reactionIds, targetTime, "init", reactionInstanceId, temperature, amountInMol)
func getJsonFromDataForReaction(whatReaction: String, reactionIds: Dictionary, targetTime: float, methodName: String, reactionInstanceId: String) -> String:
	return _getJsonFromData(whatReaction, reactionIds, targetTime, methodName, reactionInstanceId)
