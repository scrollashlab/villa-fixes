# PC phase 2 (headless): unpack inputs into ROOT, verify, run the matrix. usage: phase2.ps1 <ROOT> <STAGING>
$ErrorActionPreference = 'Stop'
$Root = $args[0]; $Stage = $args[1]
New-Item -ItemType Directory -Force -Path "$Root\logs", "$Root\tmp", "$Root\phase2", "$Root\data-do-not-redistribute\prepared", "$Root\data-do-not-redistribute\masks" | Out-Null
Start-Transcript -Path "$Root\logs\phase2.log" -Append | Out-Null
$env:TEMP = "$Root\tmp"; $env:TMP = "$Root\tmp"; $env:PYTHONDONTWRITEBYTECODE = '1'
$env:TORCH_HOME = "$Root\cache\torch"; $env:HF_HOME = "$Root\cache\hf"; $env:XDG_CACHE_HOME = "$Root\cache"
$env:UV_CACHE_DIR = "$Root\cache\uv"; $env:UV_PYTHON_INSTALL_DIR = "$Root\python"; $env:UV_PYTHON_BIN_DIR = "$Root\python\bin"
$env:UV_TOOL_DIR = "$Root\tools\uv-tools"; $env:UV_TOOL_BIN_DIR = "$Root\tools\uv-tools\bin"
$env:UV_PYTHON_INSTALL_REGISTRY = '0'; $env:UV_NO_MODIFY_PATH = '1'; $env:UV_MANAGED_PYTHON = '1'
function Check($what) { if ($LASTEXITCODE -ne 0) { Write-Output "FAILED: $what (exit $LASTEXITCODE)"; Stop-Transcript | Out-Null; exit 1 } }
$uv = Get-ChildItem -Recurse "$Root\tools\uv" -Filter uv.exe | Select-Object -First 1 -ExpandProperty FullName
$vpy = "$Root\venv\Scripts\python.exe"
# model-build imports missed by the phase-1 minimal set (found by a box smoke test): torchvision (matched to torch), timm, einops, imagecodecs (LZW TIFF)
& $uv pip install --python $vpy --index-url https://download.pytorch.org/whl/cu130 'torch==2.14.1+cu130' 'torchvision==0.29.1+cu130'; Check 'torchvision'
& $uv pip install --python $vpy 'timm==1.0.30' 'einops==0.8.2' 'imagecodecs==2026.8.16' 'huggingface-hub==2.2.0' 'safetensors==0.8.0'; Check 'model deps'
& $vpy -B -c "import torch, torchvision, timm, einops, imagecodecs; assert torch.__version__ == '2.14.1+cu130', torch.__version__; assert torch.cuda.is_available(); print('torch', torch.__version__, 'torchvision', torchvision.__version__, 'timm', timm.__version__)"; Check 'post-install check'
& $uv pip freeze --python $vpy | Out-File -Encoding utf8 "$Root\logs\pip-freeze-phase2.txt"
if ($Stage -and (Test-Path $Stage)) {
  Get-ChildItem $Stage -Filter *.py | Move-Item -Force -Destination "$Root\phase2"
  Get-ChildItem $Stage -Filter *.json | Move-Item -Force -Destination "$Root\phase2"
  Get-ChildItem $Stage -Filter *.ps1 | Move-Item -Force -Destination "$Root\phase2"
  Get-ChildItem $Stage -Filter *_mask.tif | Move-Item -Force -Destination "$Root\data-do-not-redistribute\masks"
  Get-ChildItem $Stage -Filter prep-a*.zip | Move-Item -Force -Destination "$Root\data-do-not-redistribute"
  Remove-Item -Recurse -Force $Stage
}
"DO NOT REDISTRIBUTE: CC BY-NC derived scroll data, labels, masks and predictions. Local use only." | Set-Content "$Root\data-do-not-redistribute\DO_NOT_REDISTRIBUTE.txt"
$man = Get-Content "$Root\phase2\inputs-manifest.json" -Raw | ConvertFrom-Json
foreach ($p in $man.parts) {
  $z = "$Root\data-do-not-redistribute\$($p.name)"
  if (Test-Path $z) {
    $h = (Get-FileHash $z -Algorithm SHA256).Hash.ToLower()
    if ($h -ne $p.sha256) { Write-Output "PART_SHA_MISMATCH $($p.name)"; exit 1 }
    Expand-Archive -Force $z "$Root\data-do-not-redistribute\prepared"
    Remove-Item -Force $z
    Write-Output "unpacked $($p.name) sha ok"
  }
}
New-Item -ItemType Directory -Force -Path "$Root\outputs" | Out-Null; "DO NOT REDISTRIBUTE: predictions and reduced arrays derived from CC BY-NC data. Local use only." | Set-Content "$Root\outputs\DO_NOT_REDISTRIBUTE.txt"
& $vpy -B "$Root\phase2\run_matrix.py" $Root --budget-min 15
$rc = $LASTEXITCODE
# hand-back copy for the box (CopyToBox can only read under the user profile): reduced arrays + logs only, deleted after transfer
$Out = "$env:USERPROFILE\vc-gpu-out"
New-Item -ItemType Directory -Force -Path $Out | Out-Null
Copy-Item -Force "$Root\outputs\reduced-do-not-redistribute\*.npz" $Out -ErrorAction SilentlyContinue
Copy-Item -Force "$Root\outputs\run-log.json", "$Root\logs\pip-freeze-phase2.txt" $Out -ErrorAction SilentlyContinue
Get-ChildItem $Out | ForEach-Object { Write-Output ("OUT {0} {1} {2}" -f $_.Name, $_.Length, (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower()) }
Write-Output "ROOT_SIZE_GB $([math]::Round(((Get-ChildItem $Root -Recurse -File | Measure-Object Length -Sum).Sum / 1GB), 2))"
Write-Output "DATA_SIZE_GB $([math]::Round(((Get-ChildItem "$Root\data-do-not-redistribute" -Recurse -File | Measure-Object Length -Sum).Sum / 1GB), 3))"
Write-Output "PHASE2_EXIT $rc"
Stop-Transcript | Out-Null
exit $rc
