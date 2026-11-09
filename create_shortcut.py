"""Создание ярлыка приложения в папке проекта (Windows).

Использует встроенный COM (WScript.Shell) через PowerShell —
дополнительных библиотек не требуется. Запуск: python create_shortcut.py
Вывод PowerShell читается не напрямую (кодировка консоли не гарантирована),
а через файл, который пишется в UTF-8.
"""
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
LINK_NAME = "Симулятор экономики D&D.lnk"


def _pythonw() -> str:
    """Путь к pythonw.exe (запуск без окна консоли)."""
    scripts = Path(sysconfig.get_path("scripts"))
    candidate = scripts / "pythonw.exe"
    if candidate.exists():
        return str(candidate)
    candidate = Path(sys.executable).with_name("pythonw.exe")
    if candidate.exists():
        return str(candidate)
    return sys.executable  # fallback: обычный python


def create_shortcut() -> Path:
    pythonw = _pythonw()
    main_py = PROJECT_ROOT / "main.py"
    out_file = Path(tempfile.gettempdir()) / "dnd_shortcut_path.txt"
    if out_file.exists():
        out_file.unlink()

    # пути в одинарных кавычках PowerShell; одинарная кавычка в путях
    # маловероятна (каталог профиля Windows)
    script = f"""
$ws = New-Object -ComObject WScript.Shell
$target = Join-Path '{PROJECT_ROOT}' '{LINK_NAME}'
$lnk = $ws.CreateShortcut($target)
$lnk.TargetPath = '{pythonw}'
$lnk.Arguments = '"{main_py}"'
$lnk.WorkingDirectory = '{PROJECT_ROOT}'
$lnk.Description = 'Симулятор экономики деревень D&D'
$lnk.Save()
[System.IO.File]::WriteAllText('{out_file}', $target, [System.Text.Encoding]::UTF8)
"""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
    )
    if result.returncode != 0 or not out_file.exists():
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(stderr.strip() or "не удалось создать ярлык")
    path = Path(out_file.read_text(encoding="utf-8-sig"))  # .NET пишет BOM
    out_file.unlink(missing_ok=True)
    if not path.exists():
        raise RuntimeError(f"ярлык не найден: {path}")
    return path


if __name__ == "__main__":
    try:
        path = create_shortcut()
        print(f"Ярлык создан: {path}")
    except Exception as exc:
        print(f"Не удалось создать ярлык: {exc}", file=sys.stderr)
        sys.exit(1)
