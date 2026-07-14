extends Node

var timestampMessageSent: Array
var timestampMessageReceive: Array
var timeDiffs: Array
var sumOfTimeDiffs: float
var amountOfData: int

func _process(delta: float) -> void:
	saveTimeDiffOfDataPairs()

func saveTimeDiffOfDataPairs() -> void:
	if(isDataPair()):
		var start = timestampMessageSent.pop_front()
		var end = timestampMessageReceive.pop_front()
		var timeDiff = end-start
		timeDiffs.append(timeDiff)
		sumOfTimeDiffs+=timeDiff
		amountOfData+=1
		print("last message: ", timeDiff, "ms. Average over ", amountOfData, " messages is: ", getAverageTimeDiff())

func isDataPair() -> bool:
	if(timestampMessageSent.size()!=0 and timestampMessageReceive.size() != 0):
		return true
	return false

func getAverageTimeDiff() -> float:
	return snapped((sumOfTimeDiffs/timeDiffs.size()),0.01)

func addTimestampMessageSent(timestamp: float) -> void:
	timestampMessageSent.append(timestamp)

func addTimestampMessageReceive(timestamp: float) -> void:
	timestampMessageReceive.append(timestamp)
