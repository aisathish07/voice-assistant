' Start Buddy Wake Daemon silently
' This VBS script launches the Python daemon without any visible window

Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "c:\Users\h0093\Documents\new"

' Run pythonw with the daemon script (pythonw = no console)
WshShell.Run "pythonw wakeword_daemon.pyw", 0, False
