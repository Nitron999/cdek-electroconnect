import datetime
import os
import re
import time
from typing import Callable
from playwright.sync_api import sync_playwright, Page
from storage import DOWNLOADS_DIR, add_history_entry
from printer import print_pdf_silent

CDEK_URL = "https://lk.cdek.ru/"


def _resolve_pickup_slot(
    date_str: str,
    time_from: str,
    time_to: str,
    log: Callable[[str], None],
) -> tuple[str, str, str]:
    """Если забор сегодня и время начала уже прошло — сдвигает вверх с шагом 30 мин (+3 ч интервал)."""
    now = datetime.datetime.now()
    today = now.date()

    try:
        target_date = datetime.datetime.strptime((date_str or "").strip(), "%d.%m.%Y").date()
    except Exception:
        target_date = today

    def _to_min(val: str, default_m: int) -> int:
        try:
            h, m = map(int, (val or "").strip().split(":"))
            return h * 60 + m
        except Exception:
            return default_m

    def _fmt(m: int) -> str:
        return f"{m // 60:02d}:{m % 60:02d}"

    start_m = _to_min(time_from, 12 * 60)
    end_m = _to_min(time_to, 15 * 60)
    duration = max(180, end_m - start_m)

    if target_date == today:
        now_m = now.hour * 60 + now.minute
        if now_m >= start_m:
            next_start = ((now_m // 30) + 1) * 30
            next_end = next_start + duration
            if next_end > 21 * 60:
                target_date = today + datetime.timedelta(days=1)
                next_start = 12 * 60
                next_end = 15 * 60
                log(
                    f"-> Текущее время {now.strftime('%H:%M')} — переношу забор на завтра "
                    f"{target_date.strftime('%d.%m.%Y')} 12:00-15:00"
                )
            else:
                log(
                    f"-> Автосдвиг времени забора (сейчас {now.strftime('%H:%M')}): "
                    f"{_fmt(next_start)} - {_fmt(next_end)}"
                )
            return target_date.strftime("%d.%m.%Y"), _fmt(next_start), _fmt(next_end)

    return target_date.strftime("%d.%m.%Y"), _fmt(start_m), _fmt(start_m + duration)


def _section_prefix(section_title: str) -> list[str]:
    """Возвращает XPath-префиксы заголовка секции (минуя левое меню навигации)."""
    return [
        f"//*[self::h1 or self::h2
