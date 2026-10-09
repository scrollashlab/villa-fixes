# Main run (scheduled task, hidden, no trigger; started on demand), then the task deletes itself.
# usage: mid_task.ps1 <ROOT> <NUM_WORKERS> <TASKNAME>
$Root = $args[0]; $NW = $args[1]; $Task = $args[2]
New-Item -ItemType Directory -Force -Path "$Root\logs", "$Root\tmp" | Out-Null
Start-Transcript -Path "$Root\logs\mid-task.log" -Append | Out-Null
try {
  $env:TEMP = "$Root\tmp"; $env:TMP = "$Root\tmp"; $env:PYTHONDONTWRITEBYTECODE = '1'
  $env:TORCH_HOME = "$Root\cache\torch"; $env:HF_HOME = "$Root\cache\hf"; $env:XDG_CACHE_HOME = "$Root\cache"
  $vpy = "$Root\venv\Scripts\python.exe"
  Write-Output ("MID_START " + (Get-Date -Format o))
  & $vpy -B "$Root\mid\run_mid.py" $Root run --num-workers $NW 2>&1 | Out-File -Append -Encoding utf8 "$Root\logs\mid-run.log"
  Write-Output "RUN_EXIT $LASTEXITCODE"
  & $vpy -B "$Root\mid\run_mid.py" $Root reduce 2>&1 | Out-File -Append -Encoding utf8 "$Root\logs\mid-run.log"
  Write-Output "REDUCE_EXIT $LASTEXITCODE"
  $Out = "$env:USERPROFILE\vc-gpu-out-mid"; New-Item -ItemType Directory -Force -Path $Out | Out-Null
  Copy-Item -Force "$Root\outputs\mid\stats\*.npz", "$Root\outputs\mid\run-log.json", "$Root\outputs\mid\prep-log.json", "$Root\outputs\mid\probe.json" $Out -ErrorAction SilentlyContinue
  Write-Output ("MID_END " + (Get-Date -Format o))
} finally {
  Unregister-ScheduledTask -TaskName $Task -Confirm:$false -ErrorAction SilentlyContinue
  Write-Output "TASK_REMOVED $Task"
  Stop-Transcript | Out-Null
}
