# Shared launcher (a .ps1, not an inline .bat string, since cmd->PowerShell
# quoting breaks on paths with spaces). Usage: run.ps1 [-Elevated]

param(
    [switch]$Elevated
)

$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $dir "bongo_clicker.py"

function Find-Pythonw {
    $cmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $bases = @(
        "$env:LocalAppData\Programs\Python\Python*",
        "$env:ProgramFiles\Python*",
        "${env:ProgramFiles(x86)}\Python*",
        "C:\Python*"
    )
    foreach ($pattern in $bases) {
        $found = Get-ChildItem -Path $pattern -Filter "pythonw.exe" -ErrorAction SilentlyContinue |
                 Sort-Object FullName -Descending | Select-Object -First 1
        if ($found) { return $found.FullName }
    }

    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) { return $launcher.Source }   # fallback: shows a console window

    return $null
}

if (-not (Test-Path $script)) {
    Write-Host "Could not find bongo_clicker.py next to run.ps1." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

$py = Find-Pythonw
if (-not $py) {
    Write-Host "Python not found. Install Python 3 from https://python.org (check Add to PATH)" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# A real quote char, not '\"' - backslash doesn't escape in single quotes.
$quotedScript = '"' + $script + '"'

if ($Elevated) {
    Start-Process -FilePath $py -ArgumentList $quotedScript -Verb RunAs
} else {
    Start-Process -FilePath $py -ArgumentList $quotedScript
}
