import os
import subprocess
import sys
from storage import get_app_dir


def find_sumatra() -> str | None:
    """Ищет SumatraPDF.exe рядом с программой или в ресурсах сборки."""
    candidates = [
        os.path.join(get_app_dir(), "SumatraPDF.exe"),
        os.path.join(getattr(sys, "_MEIPASS", ""), "SumatraPDF.exe"),
        r"C:\Program Files\SumatraPDF\SumatraPDF.exe",
        r"C:\Program Files (x86)\SumatraPDF\SumatraPDF.exe",
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def is_sumatra_ready() -> bool:
    return find_sumatra() is not None


def print_pdf_silent(pdf_path: str) -> tuple[bool, str]:
    """Отправляет PDF на печать через SumatraPDF.exe без диалоговых окон."""
    sumatra = find_sumatra()
    if not sumatra:
        return False, "SumatraPDF.exe не найден рядом с программой."
    if not os.path.isfile(pdf_path):
        return False, f"Файл PDF не найден: {pdf_path}"

    try:
        subprocess.run(
            [
                sumatra,
                "-print-to-default",
                "-silent",
                "-print-settings",
                "fit",
                pdf_path,
            ],
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return True, f"Отправлено на печать: {os.path.basename(pdf_path)}"
    except Exception as e:
        return False, f"Ошибка печати SumatraPDF: {e}"
