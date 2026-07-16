param(
    [Parameter(Mandatory = $true)]
    [int] $ProcessId,

    [Parameter(Mandatory = $true)]
    [string] $OutputPath
)

$ErrorActionPreference = 'Stop'

Add-Type @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

public static class ConsoleBufferReader {
    [StructLayout(LayoutKind.Sequential)]
    public struct COORD { public short X; public short Y; }

    [StructLayout(LayoutKind.Sequential)]
    public struct SMALL_RECT { public short Left, Top, Right, Bottom; }

    [StructLayout(LayoutKind.Sequential)]
    public struct CONSOLE_SCREEN_BUFFER_INFO {
        public COORD dwSize;
        public COORD dwCursorPosition;
        public short wAttributes;
        public SMALL_RECT srWindow;
        public COORD dwMaximumWindowSize;
    }

    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool FreeConsole();

    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool AttachConsole(uint processId);

    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    public static extern SafeFileHandle CreateFile(
        string name, uint access, uint share, IntPtr security,
        uint creation, uint flags, IntPtr template);

    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool GetConsoleScreenBufferInfo(
        SafeFileHandle output, out CONSOLE_SCREEN_BUFFER_INFO info);

    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    public static extern bool ReadConsoleOutputCharacter(
        SafeFileHandle output, char[] buffer, uint length,
        COORD start, out uint read);
}
'@

[ConsoleBufferReader]::FreeConsole() | Out-Null
if (-not [ConsoleBufferReader]::AttachConsole([uint32]$ProcessId)) {
    throw "AttachConsole($ProcessId) failed: $([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
}

try {
    $handle = [ConsoleBufferReader]::CreateFile(
        'CONOUT$', [uint32]2147483648, 3, [IntPtr]::Zero, 3, 0, [IntPtr]::Zero)
    if ($handle.IsInvalid) {
        throw "Opening CONOUT$ failed: $([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
    }

    $info = New-Object ConsoleBufferReader+CONSOLE_SCREEN_BUFFER_INFO
    if (-not [ConsoleBufferReader]::GetConsoleScreenBufferInfo($handle, [ref]$info)) {
        throw "GetConsoleScreenBufferInfo failed: $([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
    }

    $width = [int]$info.dwSize.X
    $height = [int]$info.dwSize.Y
    $chars = New-Object char[] ($width * $height)
    $start = New-Object ConsoleBufferReader+COORD
    $read = [uint32]0
    if (-not [ConsoleBufferReader]::ReadConsoleOutputCharacter(
        $handle, $chars, [uint32]$chars.Length, $start, [ref]$read)) {
        throw "ReadConsoleOutputCharacter failed: $([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
    }

    $lines = for ($row = 0; $row -lt $height; $row++) {
        $line = -join $chars[($row * $width)..(($row + 1) * $width - 1)]
        $line.TrimEnd()
    }
    [IO.File]::WriteAllLines($OutputPath, $lines, [Text.UTF8Encoding]::new($false))
}
catch {
    [IO.File]::WriteAllText(
        $OutputPath,
        "ERROR: $($_.Exception.Message)",
        [Text.UTF8Encoding]::new($false))
    throw
}
finally {
    [ConsoleBufferReader]::FreeConsole() | Out-Null
}
