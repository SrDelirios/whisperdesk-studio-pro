$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.Environment]::GetFolderPath('Desktop')
$ShortcutPath = Join-Path -Path $DesktopPath -ChildPath "WhisperDesk.lnk"
if (Test-Path $ShortcutPath) { Remove-Item $ShortcutPath -Force }
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "D:\Proyectos IA\Transcripciones Whisper\WhisperDesk.exe"
$Shortcut.Arguments = ""
$Shortcut.WorkingDirectory = "D:\Proyectos IA\Transcripciones Whisper"
$Shortcut.IconLocation = "D:\Proyectos IA\Transcripciones Whisper\icon.ico,0"
$Shortcut.Description = "WhisperDesk Studio Pro - Transcripción Inteligente y Actas IA"
$Shortcut.Save()

# Notificar al explorador de Windows que refresque los íconos
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class ShellNotifier {
    [DllImport("shell32.dll", CharSet = CharSet.Auto, SetLastError = true)]
    public static extern void SHChangeNotify(uint wEventId, uint uFlags, IntPtr dwItem1, IntPtr dwItem2);
}
"@
[ShellNotifier]::SHChangeNotify(0x08000000, 0x0000, [IntPtr]::Zero, [IntPtr]::Zero)

Write-Host "Acceso directo nativo con icono de alta legibilidad creado y actualizado exitosamente"
