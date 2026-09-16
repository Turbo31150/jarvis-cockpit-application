<#
real.ps1 — pilote la VRAIE fenêtre du cockpit sur le bureau Windows (pas offscreen).
  -Restart          tue l'instance en cours et relance NON-admin (explorer.exe → .cmd → pythonw .venv)
  -Click <regex>    clique le premier bouton dont le nom UIA matche (ex. 'Terminal JARVIS')
  -Out <png>        capture PrintWindow de la fenêtre (défaut %TEMP%\jarvis-cockpit-driver\real-window.png)
Sortie : PID/titre de la fenêtre, chemin PNG, processus shell/terminal créés après le clic.
Exécuter avec : powershell -NoProfile -ExecutionPolicy Bypass -File real.ps1 [-Restart] [-Click 'Terminal JARVIS']
(Le fichier porte un BOM UTF-8 : PowerShell 5.1 lirait sinon les accents en ANSI et casserait l'analyse.)
#>
param([switch]$Restart, [string]$Click, [string]$Out = "$env:TEMP\jarvis-cockpit-driver\real-window.png")
$ErrorActionPreference = 'Continue'
$racine = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
if ($Restart) {
  Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'jarvis_cockpit_launcher\.pyw' -and $_.CommandLine -notmatch '--web' } |
    ForEach-Object { "arrêt instance PID $($_.ProcessId)"; Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  Start-Sleep 2
  $cmd = "$env:TEMP\jarvis-cockpit-real-launch.cmd"
  "@echo off`r`nstart `"`" `"$racine\.venv\Scripts\pythonw.exe`" `"$racine\jarvis_cockpit_launcher.pyw`"`r`n" | Set-Content -Path $cmd -Encoding Ascii
  Start-Process explorer.exe $cmd      # explorer = niveau d'intégrité moyen → cockpit non-admin, comme un double-clic
}
$deadline = (Get-Date).AddSeconds(40); $main = $null
while ((Get-Date) -lt $deadline) {
  $main = Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -match 'JARVIS' } | Select-Object -First 1
  if ($main) { break }; Start-Sleep 2
}
if (-not $main) { "fenêtre JARVIS introuvable (lancer avec -Restart ?)"; exit 1 }
"fenêtre : PID $($main.Id) démarrée $($main.StartTime) — $($main.MainWindowTitle)"
Start-Sleep 5
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public class JcWin { [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; } }
"@
$h = $main.MainWindowHandle; [JcWin]::SetForegroundWindow($h) | Out-Null; Start-Sleep 1
$r = New-Object JcWin+RECT; [JcWin]::GetWindowRect($h, [ref]$r) | Out-Null
$bmp = New-Object System.Drawing.Bitmap(($r.R - $r.L), ($r.B - $r.T)); $g = [System.Drawing.Graphics]::FromImage($bmp)
$dc = $g.GetHdc(); [JcWin]::PrintWindow($h, $dc, 2) | Out-Null; $g.ReleaseHdc($dc)
New-Item -ItemType Directory -Force -Path (Split-Path $Out) | Out-Null
$bmp.Save($Out); "capture réelle : $Out ($($bmp.Width)x$($bmp.Height))"
if ($Click) {
  Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
  $root = [System.Windows.Automation.AutomationElement]::RootElement
  $cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, $main.Id)
  $win = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $cond)
  if (-not $win) { "UIA : fenêtre non trouvée"; exit 2 }
  $btnCond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty, [System.Windows.Automation.ControlType]::Button)
  $btns = $win.FindAll([System.Windows.Automation.TreeScope]::Descendants, $btnCond)
  $target = $btns | Where-Object { $_.Current.Name -match $Click } | Select-Object -First 1
  if (-not $target) { "bouton '$Click' introuvable parmi $($btns.Count) : " + (($btns | ForEach-Object { $_.Current.Name }) -join ' | '); exit 3 }
  $t0 = Get-Date
  $target.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
  "clic UIA : $($target.Current.Name) à $($t0.ToString('HH:mm:ss'))"
  Start-Sleep 6
  "--- processus shell/terminal créés depuis le clic :"
  Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'pwsh|powershell|cmd\.exe|WindowsTerminal|OpenConsole|conhost' -and $_.CreationDate -gt $t0.AddSeconds(-1) } |
    Select-Object ProcessId, ParentProcessId, Name, @{n='Cmd';e={ if ($_.CommandLine) { $_.CommandLine.Substring(0,[Math]::Min(140,$_.CommandLine.Length)) } }} | Format-Table -AutoSize | Out-String -Width 220
}
