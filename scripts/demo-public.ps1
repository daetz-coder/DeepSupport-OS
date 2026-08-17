# DeepSupport OS — Docker-only public demo (same-origin UI + tunnel)
# Usage (repo root):
#   powershell -ExecutionPolicy Bypass -File scripts\demo-public.ps1
# Options:
#   -TunnelMode cloudflare|localtunnel|none   (default: cloudflare)
#     cloudflare : Cloudflare quick tunnel -> https://<rand>.trycloudflare.com (no account, no interstitial)
#     localtunnel: branded URL -> https://deepsupport-os.loca.lt (may show a password page to visitors)
#     none       : start stack only; tunnel yourself to :5173 (same as -SkipTunnel)
#   -SkipTunnel  (legacy alias for -TunnelMode none)

param(
  [string]$TunnelMode = "cloudflare",
  [switch]$SkipTunnel,
  [int]$WaitDockerSeconds = 120,
  [int]$WaitHealthSeconds = 600
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if ($SkipTunnel) { $TunnelMode = "none" }

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

function Wait-PublicReady {
  param([string]$Url, [int]$Seconds)
  $deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $u = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 15
      if ($u.StatusCode -eq 200) { return $true }
    } catch {}
    Start-Sleep -Seconds 5
  }
  return $false
}

if (-not (Test-Path "$Root\.env")) {
  throw "Missing .env — copy .env.example and set DEEPSEEK_API_KEY"
}

$raglabEnv = Join-Path (Split-Path $Root -Parent) "RAGLab\.env"
if (-not (Test-Path $raglabEnv)) {
  throw "Missing ../RAGLab/.env — copy RAGLab .env.example and set keys/models"
}

$keyOk = Select-String -Path "$Root\.env" -Pattern '^DEEPSEEK_API_KEY=.+' -Quiet
if (-not $keyOk) {
  Write-Warning "DEEPSEEK_API_KEY looks empty; agent runs will fail."
}

$adminOk = Select-String -Path "$Root\.env" -Pattern '^ADMIN_TOKEN=.+' -Quiet
if ($TunnelMode -ne "none" -and -not $adminOk) {
  Write-Warning "ADMIN_TOKEN is empty — /api/meta/* (Skills/MCP toggles) and /admin/seed are open without auth. Set ADMIN_TOKEN in .env before exposing publicly."
}

$publicPort = 5173

Write-Host "== Docker Compose (DeepSupport + RAGLab) =="
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
    throw "Docker daemon not ready within ${WaitDockerSeconds}s. Start Docker Desktop and re-run."
  }
}

Write-Host "Building and starting compose (RAGLab model load may take several minutes)..."
docker compose up --build -d
if ($LASTEXITCODE -ne 0) { throw "docker compose failed" }

Write-Host "Waiting for health (api + UI + RAGLab via /api/health/deps)..."
$healthy = $false
$deadline = (Get-Date).AddSeconds($WaitHealthSeconds)
while ((Get-Date) -lt $deadline) {
  try {
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:18000/health" -TimeoutSec 3
    $ui = Invoke-WebRequest -Uri "http://127.0.0.1:5173/" -UseBasicParsing -TimeoutSec 3
    $deps = Invoke-RestMethod -Uri "http://127.0.0.1:18000/api/health/deps" -TimeoutSec 10
    $ragOk = $deps.raglab.ok -eq $true
    if ($h.status -eq "ok" -and $ui.StatusCode -eq 200 -and $ragOk) {
      $healthy = $true
      break
    }
    if ($h.status -eq "ok" -and $ui.StatusCode -eq 200 -and -not $ragOk) {
      Write-Host ("  waiting RAGLab... error={0}" -f $deps.raglab.error)
    }
  } catch { Start-Sleep -Seconds 5 }
  Start-Sleep -Seconds 5
}
if (-not $healthy) { throw "Services not healthy. Check: docker compose logs && curl http://127.0.0.1:18000/api/health/deps" }

Write-Host "Local OK:"
Write-Host "  UI        http://127.0.0.1:5173"
Write-Host "  API       http://127.0.0.1:18000/health"
Write-Host "  RAGLab    http://127.0.0.1:18001/api/health  (container DNS: raglab:8000)"
Write-Host "  RAGLab UI http://127.0.0.1:18080"
Write-Host "  deps      http://127.0.0.1:18000/api/health/deps  raglab.ok=true"

if ($TunnelMode -eq "none") {
  Write-Host "Tunnel disabled. Share only after you start a tunnel to port $publicPort."
  exit 0
}

Write-Host ""
Write-Host "== Public tunnel ($TunnelMode) =="

if ($TunnelMode -eq "cloudflare") {
  Ensure-Cloudflared | Out-Null
  $log = Join-Path $env:TEMP "cloudflared-tunnel.log"
  Write-Host "Starting Cloudflare quick tunnel -> http://127.0.0.1:$publicPort (log: $log)"
  Write-Host "Keep this window open. Ctrl+C stops the tunnel (compose keeps running)."
  $proc = Start-Process -FilePath (Ensure-Cloudflared) -ArgumentList @("tunnel", "--url", "http://127.0.0.1:$publicPort", "--no-autoupdate") `
    -RedirectStandardOutput $log -RedirectStandardError "$log.err" -PassThru -NoNewWindow
  $url = $null
  $urlDeadline = (Get-Date).AddSeconds(60)
  while ((Get-Date) -lt $urlDeadline) {
    Start-Sleep -Seconds 2
    if ($proc.HasExited) { throw "cloudflared exited early (code $($proc.ExitCode)); see $log" }
    $m = Select-String -Path $log, "$log.err" -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($m) { $url = $m.Matches[0].Value; break }
  }
  if (-not $url) { throw "Could not read public URL from cloudflared log: $log" }
  if (-not (Wait-PublicReady -Url $url -Seconds 90)) {
    Write-Warning "Public URL not answering yet — it may need a minute; retry in a browser: $url"
  }
  Write-Host ""
  Write-Host "PUBLIC URL: $url"
  Write-Host "Share this link. It maps the same-origin UI + /api + /health (nginx -> api)."
  $proc.WaitForExit()
} else {
  # localtunnel (branded URL; visitors may see a loca.lt interstitial)
  $npx = Get-Command npx -ErrorAction SilentlyContinue
  if (-not $npx) { throw "npx not found — install Node.js or use -TunnelMode cloudflare" }
  Write-Host "Trying https://deepsupport-os.loca.lt ..."
  Write-Host "If loca.lt shows a password page, enter THIS machine's public IP."
  Write-Host "Keep this window open. Ctrl+C stops the tunnel (compose keeps running)."
  Write-Host "PUBLIC URL: https://deepsupport-os.loca.lt"
  npx --yes localtunnel --port $publicPort --subdomain deepsupport-os
}
