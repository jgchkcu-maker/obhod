"""Create a per-user desktop shortcut, without changing the system PATH."""
import sys
from pathlib import Path


def create(root=None):
    import win32com.client
    from win32com.shell import shell, shellcon
    root = Path(root or Path(__file__).resolve().parents[1]).resolve()
    executable = root / "dist/Obhod/Obhod.exe"
    shell_link = win32com.client.Dispatch("WScript.Shell")
    desktop = Path(shell.SHGetFolderPath(0, shellcon.CSIDL_DESKTOPDIRECTORY, None, 0))
    target = desktop / "Обход.lnk"
    link = shell_link.CreateShortcut(str(target))
    if executable.exists():
        link.TargetPath = str(executable)
        link.Arguments = ""
        link.WorkingDirectory = str(executable.parent)
        link.IconLocation = str(executable) + ",0"
    else:
        link.TargetPath = str(root / ".venv/Scripts/pythonw.exe")
        link.Arguments = "-m obhod"
        link.WorkingDirectory = str(root)
        icon = root / "data/obhod.ico"
        if icon.exists():
            link.IconLocation = str(icon)
    link.Description = "Обход · YouTube, Discord, Fortnite"
    link.Save()
    print(target)
    return target


if __name__ == "__main__":
    create(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
