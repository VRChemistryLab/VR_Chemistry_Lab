cd /d "%~dp0"
@echo off
echo Starting Cantera server...
start "" "server\cantera\websocket_server.exe"

echo Waiting for servers to be ready...
timeout /t 3 /nobreak

echo Starting VR App...
start "" "godot\VRApp.exe"