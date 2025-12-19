@echo off
echo Starting Sovereign Console Server...

echo.
echo Local Access: http://localhost:8000/

echo.
echo Network Access (for phone/other devices):
for /f "tokens=*" %%a in ('python -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('8.8.8.8', 80)); print(s.getsockname()[0]); s.close()"') do set IP=%%a
echo http://%IP%:8000/
echo.

cd tools
python -m http.server 8000
pause