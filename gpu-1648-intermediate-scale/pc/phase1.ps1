# Pre-seal phase (headless): psutil into the venv, level-0 mask-box download + S9/S4 inputs, step-0b loader probe.
# usage: phase1.ps1 <ROOT>
$Root = $args[0]
New-Item -ItemType Directory -Force -Path "$Root\logs", "$Root\tmp", "$Root\mid" | Out-Null
Start-Transcript -Path "$Root\logs\mid-phase1.log" -Append | Out-Null
$env:TEMP = "$Root\tmp"; $env:TMP = "$Root\tmp"; $env:PYTHONDONTWRITEBYTECODE = '1'; $env:UV_CACHE_DIR = "$Root\cache\uv"
$env:TORCH_HOME = "$Root\cache\torch"; $env:HF_HOME = "$Root\cache\hf"; $env:XDG_CACHE_HOME = "$Root\cache"
function Check($what) { if ($LASTEXITCODE -ne 0) { Write-Output "FAILED: $what (exit $LASTEXITCODE)"; Stop-Transcript | Out-Null; exit 1 } }
$vpy = "$Root\venv\Scripts\python.exe"
Copy-Item -Force "$Root\lfs\heldout-plan.json" "$Root\mid\heldout-plan.json"
& $vpy -B -c "import psutil" 2>$null
if ($LASTEXITCODE -ne 0) {
  $uv = Get-ChildItem -Path "$Root\tools" -Recurse -Filter uv.exe -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($uv) { & $uv.FullName pip install --python $vpy psutil } else { & $vpy -m pip install psutil }
  & $vpy -B -c "import psutil; print('psutil', psutil.__version__)"; Check 'psutil'
}
& $vpy -B "$Root\mid\run_mid.py" $Root prep; Check 'prep'
& $vpy -B "$Root\mid\run_mid.py" $Root probe; Check 'probe'
Write-Output "PHASE1_DONE"
Stop-Transcript | Out-Null
