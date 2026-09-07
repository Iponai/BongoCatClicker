# Creates .lnk shortcuts with the cat icon (Windows won't let a .bat have
# its own icon, only a shortcut can). Run once after cloning:
#   powershell -File tools\make_shortcuts.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$icon = Join-Path $root "assets\cat_icon.ico"
$shell = New-Object -ComObject WScript.Shell

function New-CatShortcut($linkName, $targetBat) {
    $lnkPath = Join-Path $root $linkName
    $sc = $shell.CreateShortcut($lnkPath)
    $sc.TargetPath = "cmd.exe"
    $sc.Arguments = '/c ""' + (Join-Path $root $targetBat) + '""'
    $sc.WorkingDirectory = $root
    $sc.IconLocation = $icon
    $sc.WindowStyle = 7   # minimized cmd window while it launches
    $sc.Save()
    Write-Output ("Created: {0}" -f $lnkPath)
}

New-CatShortcut "BongoCatClicker.lnk" "start.bat"
New-CatShortcut "BongoCatClicker (admin).lnk" "start_as_admin.bat"
