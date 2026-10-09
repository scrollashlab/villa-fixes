' Starts mid_task.ps1 with no visible window (window style 0) from an interactive-session scheduled task.
Set sh = CreateObject("WScript.Shell")
sh.Run "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File ""__ROOT__\mid\mid_task.ps1"" ""__ROOT__"" __NW__ __TASK__", 0, True
