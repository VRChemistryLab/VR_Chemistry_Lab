extends Node

var dataBlock

func getData(jsonData):
	assert(jsonData != null)
	if(jsonData != null):
		var loadedData = parseJson(jsonData)
		if(loadedData != null):
			# New unified server envelope:
			# { "success": bool, "reactionInstanceId": ..., "reactionIds": {...},
			#   "data": {"dataBlockList": [...]} | {"sessionClosed": bool} | null,
			#   "error": {"code": str, "message": str} | null }
			# "success" defaults to true so older/edge-case messages that
			# don't set it explicitly still parse instead of getting flagged
			# as errors.
			var success: bool = loadedData.get("success", true)
			if not success:
				var err: Dictionary = loadedData.get("error", {})
				print("ServerHandler: server reported an error [", err.get("code", "UNKNOWN"), "]: ", err.get("message", ""))

			var dataPayload = loadedData.get("data")
			if dataPayload == null:
				dataPayload = {}
			var dataArray: Array = dataPayload.get("dataBlockList", [])
			var reactionIds: Dictionary = loadedData.get("reactionIds")
			assert(reactionIds!=null and reactionIds.size()>0)
			if(dataArray==null or dataArray.size()==0):
				print("a message without dataBlockList was received")
			return [dataArray, reactionIds]
		else:
			print("there is a message, but it is not json parsable. Might be an error from the server: ", jsonData)
	else:
		print("no data yet")
	return null


func parseJson(json):
	var jsonObject = JSON.new()
	jsonObject.parse(json)
	#store parsed data in data block dictionary
	dataBlock = jsonObject.data
	return dataBlock
