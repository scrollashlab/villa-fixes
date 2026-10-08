# Self-contained GPU setup. Everything under $Root; no PATH/registry changes; console only (no windows).
$ErrorActionPreference = 'Stop'
$Root = $args[0]
$Log = Join-Path $Root 'logs\setup.log'
New-Item -ItemType Directory -Force -Path (Join-Path $Root 'logs'), (Join-Path $Root 'tmp'), (Join-Path $Root 'tools\uv') | Out-Null
Start-Transcript -Path $Log -Append | Out-Null
$env:TEMP = Join-Path $Root 'tmp'; $env:TMP = $env:TEMP
$env:UV_CACHE_DIR = Join-Path $Root 'cache\uv'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $Root 'python'
$env:UV_PYTHON_BIN_DIR = Join-Path $Root 'python\bin'
$env:UV_TOOL_DIR = Join-Path $Root 'tools\uv-tools'
$env:UV_TOOL_BIN_DIR = Join-Path $Root 'tools\uv-tools\bin'
$env:UV_PYTHON_INSTALL_REGISTRY = '0'
$env:UV_NO_MODIFY_PATH = '1'
$env:UV_MANAGED_PYTHON = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:TORCH_HOME = Join-Path $Root 'cache\torch'; $env:HF_HOME = Join-Path $Root 'cache\hf'; $env:XDG_CACHE_HOME = Join-Path $Root 'cache'
$B = Join-Path $Root 'bootstrap'
function Check($what) { if ($LASTEXITCODE -ne 0) { Write-Output "FAILED: $what (exit $LASTEXITCODE)"; Stop-Transcript | Out-Null; exit 1 } }
Expand-Archive -Force (Join-Path $B 'uv-x86_64-pc-windows-msvc.zip') (Join-Path $Root 'tools\uv')
$uv = Get-ChildItem -Recurse (Join-Path $Root 'tools\uv') -Filter uv.exe | Select-Object -First 1 -ExpandProperty FullName
& $uv --version; Check 'uv'
& $uv python install 3.14 --no-bin --no-registry --install-dir $env:UV_PYTHON_INSTALL_DIR; Check 'python install'
$py = Get-ChildItem $env:UV_PYTHON_INSTALL_DIR -Directory -Filter 'cpython-3.14*' | Select-Object -First 1 | ForEach-Object { Join-Path $_.FullName 'python.exe' }
Write-Output "managed python: $py"
& $uv venv --python $py (Join-Path $Root 'venv'); Check 'venv'
$vpy = Join-Path $Root 'venv\Scripts\python.exe'
& $uv pip install --python $vpy --index-url https://download.pytorch.org/whl/cu130 'torch==2.14.1+cu130'; Check 'torch'
& $uv pip install --python $vpy 'numpy==2.5.3' 'zarr==3.4.1' 'numcodecs==0.16.5' 'fsspec==2026.9.0' 's3fs==2026.9.0' 'tifffile==2026.9.20' 'pyyaml==6.0.3' 'requests==2.34.2' 'pillow==12.3.0' 'cachetools==7.2.1' 'pynrrd==1.1.3' 'edt==3.1.2' 'scipy==1.18.1'; Check 'deps'
Expand-Archive -Force (Join-Path $B 'villa-vesuvius-src-8b63a2652.zip') (Join-Path $Root 'villa-8b63a2652')
& $uv pip freeze --python $vpy | Out-File -Encoding utf8 (Join-Path $Root 'logs\pip-freeze.txt')
& $vpy -B (Join-Path $B 'gpu_check.py') (Join-Path $Root 'villa-8b63a2652\vesuvius\src') | Tee-Object -FilePath (Join-Path $Root 'logs\gpu-check.json'); Check 'gpu_check'
& $vpy -B (Join-Path $B 'fetch_ckpts.py') (Join-Path $Root 'ckpt'); Check 'ckpts'
$size = (Get-ChildItem -Recurse -File $Root -ErrorAction SilentlyContinue | Measure-Object -Sum Length).Sum
Write-Output ("ROOT_SIZE_GB {0:N2}" -f ($size / 1GB))
Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='D:'" | ForEach-Object { Write-Output ("D_FREE_GB {0:N1}" -f ($_.FreeSpace / 1GB)) }
Write-Output 'SETUP_DONE'
Stop-Transcript | Out-Null
