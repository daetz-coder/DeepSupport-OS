# DeepSupport OS — public interview demo (same-origin UI + Cloudflare Tunnel)
# Usage (repo root):
#   powershell -ExecutionPolicy Bypass -File scripts\demo-public.ps1
# Optional: -LocalDev  (skip Docker; vite proxy + empty VITE_API_BASE)

param(
  [switch]$LocalDev,
  [switch]$SkipTunnel,
  [int]$WaitDockerSeconds = 120
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Wait-Docker {
  param([int]$Seconds)
  $deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $deadline) {
    try {
      docker info --format '{{.ServerVersion}}' 2>$null | Out-Null
      if ($LASTEXITCODE -eq 0) { return $true }
    } catch {}
    Start-Sleep -Seconds 3
  }
  return $false
}

function Ensure-Cloudflared {
  $cmd = Get-Command cloudflared -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  $winget = Get-Command winget -ErrorAction SilentlyContinue
  if (-not $winget) {
    throw "cloudflared not found. Install: winget install Cloudflare.cloudflared"
  }
  Write-Host "Installing cloudflared..."
  winget install --id Cloudflare.cloudflared -e --accept-package-agreements --accept-source-agreements
  $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
    [System.Environment]::GetEnvironmentVariable("Path", "User")
  $cmd = Get-Command cloudflared -ErrorAction SilentlyContinue
  if (-not $cmd) { throw "cloudflared installed but not on PATH; open a new terminal and re-run." }
  return $cmd.Source
}

if (-not (Test-Path "$Root\.env")) {
  throw "Missing .env — copy .env.example and set DEEPSEEK_API_KEY"
}

$keyOk = Select-String -Path "$Root\.env" -Pattern '^DEEPSEEK_API_KEY=.+' -Quiet
if (-not $keyOk) {
  Write-Warning "DEEPSEEK_API_KEY looks empty; agent runs will fail."
}

$publicPort = 5173

if ($LocalDev) {
  Write-Host "== LocalDev mode: backend :8000 + vite :5173 (proxy, same-origin) =="
  $apiHost = (Select-String -Path "$Root\.env" -Pattern '^API_HOST=(.+)$').Matches.Groups[1].Value
  if ($apiHost -and $apiHost -ne "127.0.0.1" -and $apiHost -ne "0.0.0.0") {
    Write-Host "API_HOST=$apiHost"
  }

  Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$Root\backend'; uv sync; uv run deepsupport-os"
  )
  Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$Root\frontend'; if (-not (Test-Path node_modules)) { npm install }; `$env:VITE_API_BASE=''; npm run dev -- --host 0.0.0.0 --port 5173"
  )
  Write-Host "Waiting for UI http://127.0.0.1:5173 ..."
  $ok = $false
  for ($i = 0; $i -lt 60; $i++) {
    try {
      $r = Invoke-WebRequest -Uri "http://127.0.0.1:5173/" -UseBasicParsing -TimeoutSec 2
      if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch { Start-Sleep -Seconds 2 }
  }
  if (-not $ok) { throw "Frontend did not become ready on :5173" }
} else {
  Write-Host "== Docker Compose mode (recommended) =="
  $dd = "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
  try {
    docker info 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "docker not ready" }
  } catch {
    if (Test-Path $dd) {
      Write-Host "Starting Docker Desktop..."
      Start-Process $dd
    }
    if (-not (Wait-Docker -Seconds $WaitDockerSeconds)) {
      throw "Docker daemon not ready within ${WaitDockerSeconds}s. Start Docker Desktop, or re-run with -LocalDev"
    }
  }

  Write-Host "Building and starting compose..."
  docker compose up --build -d
  if ($LASTEXITCODE -ne 0) { throw "docker compose failed" }

  Write-Host "Waiting for health..."
  $healthy = $false
  for ($i = 0; $i -lt 60; $i++) {
    try {
      $h = Invoke-RestMethod -Uri "http://127.0.0.1:18000/health" -TimeoutSec 2
      $ui = Invoke-WebRequest -Uri "http://127.0.0.1:5173/" -UseBasicParsing -TimeoutSec 2
      if ($h.status -eq "ok" -and $ui.StatusCode -eq 200) { $healthy = $true; break }
    } catch { Start-Sleep -Seconds 3 }
  }
  if (-not $healthy) { throw "Services not healthy. Check: docker compose logs" }
  Write-Host "Local OK: UI http://127.0.0.1:5173  API http://127.0.0.1:18000/health"
}

if ($SkipTunnel) {
  Write-Host "SkipTunnel set. Share only after you start a tunnel to port $publicPort."
  exit 0
}

Ensure-Cloudflared | Out-Null
Write-Host ""
Write-Host "Prefer branded URL via localtunnel (DeepSupportOS in hostname)."
Write-Host "Fallback: Cloudflare quick tunnel (random *.trycloudflare.com)."
Write-Host "Keep this window open. Ctrl+C stops the tunnel (compose keeps running)."
Write-Host ""

$npx = Get-Command npx -ErrorAction SilentlyContinue
if ($npx) {
  Write-Host "Trying https://deepsupport-os.loca.lt ..."
  Write-Host "If loca.lt shows a password page, enter THIS machine's public IP."
  npx --yes localtunnel --port $publicPort --subdomain deepsupport-os
} else {
  cloudflared tunnel --url "http://127.0.0.1:$publicPort"
}
