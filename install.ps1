<#
    creds-vault installer (Windows, PowerShell)

    Copies the broker into %USERPROFILE%\.creds and puts that folder on the
    current user's PATH so `creds` works from any new shell.

    Usage:
        powershell -ExecutionPolicy Bypass -File .\install.ps1

    Created by Alorny AI (https://alorny.cloud) - Hieronymos Junior Starch, Founder.
    Contact: contact@alorny.cloud | WhatsApp +263 71 441 2862
#>

$ErrorActionPreference = "Stop"

$source = $PSScriptRoot
$target = Join-Path $env:USERPROFILE ".creds"

Write-Host "creds-vault installer" -ForegroundColor Cyan
Write-Host ""

# 1. Python present?
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "FAIL: python was not found on PATH." -ForegroundColor Red
    Write-Host "Install Python 3.8 or newer from https://python.org and re-run this script."
    exit 1
}
$pyver = (& python --version) 2>&1
Write-Host "Found $pyver at $($python.Source)"

# 2. Windows only (DPAPI is a Windows API)
if (-not $IsWindows -and $PSVersionTable.PSVersion.Major -ge 6) {
    Write-Host "FAIL: creds-vault uses the Windows DPAPI and only runs on Windows." -ForegroundColor Red
    exit 1
}

# 3. Create the target folder
if (-not (Test-Path $target)) {
    New-Item -ItemType Directory -Path $target | Out-Null
    Write-Host "Created $target"
} else {
    Write-Host "Using existing $target"
}

# 4. Copy the broker files. Never overwrite an existing store.
Copy-Item (Join-Path $source "creds.py")  -Destination $target -Force
Copy-Item (Join-Path $source "creds.cmd") -Destination $target -Force
Write-Host "Copied creds.py and creds.cmd"

if (Test-Path (Join-Path $target "store.bin")) {
    Write-Host "Existing store.bin left untouched (your secrets are safe)." -ForegroundColor Yellow
}

# 5. Add to the user PATH if it is not already there
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$target*") {
    $newPath = if ([string]::IsNullOrEmpty($userPath)) { $target } else { "$userPath;$target" }
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "Added $target to your user PATH."
    Write-Host "Open a NEW terminal for the `creds` command to resolve." -ForegroundColor Yellow
} else {
    Write-Host "$target is already on your user PATH."
}

# 6. Smoke test through the real entry point
Write-Host ""
Write-Host "Verifying..." -ForegroundColor Cyan
& python (Join-Path $target "creds.py") set creds-vault-install-check --value ok | Out-Null
$readback = & python (Join-Path $target "creds.py") get creds-vault-install-check
& python (Join-Path $target "creds.py") delete creds-vault-install-check | Out-Null

if ($readback -eq "ok") {
    Write-Host "PASS: set, get and delete all worked. Encrypted store is at $target\store.bin" -ForegroundColor Green
} else {
    Write-Host "FAIL: round trip returned '$readback' instead of 'ok'." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Next steps:"
Write-Host "  echo YOUR_KEY_VALUE | creds set openai-api-key"
Write-Host "  creds list"
Write-Host "  creds get openai-api-key"
Write-Host ""
Write-Host "Then paste AGENTS.md into your agent's instruction file so it uses the vault."
