@echo off
pyside6-designer
if errorlevel 1 (
  echo.
  echo Qt Designer nije pronadjen. Instaliraj PySide6: py -m pip install PySide6
  pause
)
