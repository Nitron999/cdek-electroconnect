import json
import os
import sys
import datetime


def get_app_dir() -> str:
    """Возвращает папку, в которой лежит .exe или скрипт."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


RECIPIENTS_FILE = os.path.join(get_app_dir(), "recipients.json")
HISTORY_FILE = os.path.join(get_app_dir(), "history.json")
DOWNLOADS_DIR = os.path.join(get_app_dir(), "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

DEFAULT_RECIPIENTS = [
    {
        "name": "Патрушев Илья Сергеевич",
        "template": "Патрушев Илья Сергеевич",
        "recipient_type": "ФИЗ. ЛИЦО",
        "phone": "+7 950 152 10 79",
        "email": "",
        "city_to": "Ижевск, Удмуртия, Россия",
        "pvz_address": "ул. Азина, 135",
        "delivery_to": "В ПВЗ",
        "tariff": "Экспресс дверь-склад",
    }
]


def load_recipients() -> list[dict]:
    if not os.path.exists(RECIPIENTS_FILE):
        save_recipients(DEFAULT_RECIPIENTS)
        return list(DEFAULT_RECIPIENTS)
    try:
        with open(RECIPIENTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return list(DEFAULT_RECIPIENTS)


def save_recipients(items: list[dict]) -> None:
    with open(RECIPIENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def load_history() -> list[dict]:
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def add_history_entry(entry: dict) -> None:
    history = load_history()
    entry["created_at"] = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    history.insert(0, entry)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history[:200], f, ensure_ascii=False, indent=2)
