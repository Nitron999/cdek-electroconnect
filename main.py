import datetime
import json
import queue
import re
import threading
import flet as ft
from storage import load_recipients, save_recipients, load_history, HISTORY_FILE
from printer import is_sumatra_ready
from cdek_pvz import fetch_cdek_pvz
from cdek_worker import run_cdek_order


THEMES = {
    "Тёмная ночь": {
        "mode": ft.ThemeMode.DARK,
        "bold_ui": False,
        "page_bg": "#0b0f19",
        "sidebar_bg": "#111827",
        "card_bg": "#151d2e",
        "recip_card_bg": "#1f1a14",
        "subcard_bg": "#101725",
        "input_bg": "#0b101b",
        "item_bg": "#161f30",
        "item_selected_bg": "#0f2e24",
        "footer_bg": "#131a29",
        "log_bg": "#080c14",
        "border": "#26334a",
        "input_border": "#334155",
        "text_primary": "#ffffff",
        "text_secondary": "#94a3b8",
        "text_checkbox": "#e2e8f0",
        "pvz_addr": "#fde047",
        "accents": {
            "order": "#38bdf8",
            "sender": "#60a5fa",
            "recip": "#ff9f1c",
            "goods": "#c084fc",
            "ship": "#34d399",
            "comment": "#fb7185",
        },
    },
    "Светлая классика": {
        "mode": ft.ThemeMode.LIGHT,
        "bold_ui": True,
        "page_bg": "#f1f5f9",
        "sidebar_bg": "#ffffff",
        "card_bg": "#ffffff",
        "recip_card_bg": "#fff7ed",
        "subcard_bg": "#f8fafc",
        "input_bg": "#ffffff",
        "item_bg": "#f8fafc",
        "item_selected_bg": "#dcfce7",
        "footer_bg": "#ffffff",
        "log_bg": "#f1f5f9",
        "border": "#cbd5e1",
        "input_border": "#64748b",
        "text_primary": "#090d16",
        "text_secondary": "#1e293b",
        "text_checkbox": "#090d16",
        "pvz_addr": "#92400e",
        "accents": {
            "order": "#0369a1",
            "sender": "#2563eb",
            "recip": "#ea580c",
            "goods": "#6d28d9",
            "ship": "#047857",
            "comment": "#be123c",
        },
    },
    "Изумруд СДЭК": {
        "mode": ft.ThemeMode.DARK,
        "bold_ui": False,
        "page_bg": "#061410",
        "sidebar_bg": "#0a1f19",
        "card_bg": "#0e2921",
        "recip_card_bg": "#1e1f12",
        "subcard_bg": "#091c16",
        "input_bg": "#061510",
        "item_bg": "#113128",
        "item_selected_bg": "#14532d",
        "footer_bg": "#0a1f19",
        "log_bg": "#040d0a",
        "border": "#1d4d3e",
        "input_border": "#286653",
        "text_primary": "#f0fdf4",
        "text_secondary": "#86efac",
        "text_checkbox": "#dcfce7",
        "pvz_addr": "#fde047",
        "accents": {
            "order": "#34d399",
            "sender": "#38bdf8",
            "recip": "#ff9f1c",
            "goods": "#a78bfa",
            "ship": "#4ade80",
            "comment": "#fb7185",
        },
    },
    "Глубокий океан": {
        "mode": ft.ThemeMode.DARK,
        "bold_ui": False,
        "page_bg": "#071120",
        "sidebar_bg": "#0b192e",
        "card_bg": "#0f223d",
        "recip_card_bg": "#1e1a14",
        "subcard_bg": "#0a172b",
        "input_bg": "#071222",
        "item_bg": "#13294a",
        "item_selected_bg": "#113a4b",
        "footer_bg": "#0b192e",
        "log_bg": "#050c17",
        "border": "#1e3a5f",
        "input_border": "#2c5282",
        "text_primary": "#f0f9ff",
        "text_secondary": "#7dd3fc",
        "text_checkbox": "#e0f2fe",
        "pvz_addr": "#fde047",
        "accents": {
            "order": "#38bdf8",
            "sender": "#60a5fa",
            "recip": "#ff9f1c",
            "goods": "#c084fc",
            "ship": "#2dd4bf",
            "comment": "#f472b6",
        },
    },
    "Графит и золото": {
        "mode": ft.ThemeMode.DARK,
        "bold_ui": False,
        "page_bg": "#121212",
        "sidebar_bg": "#1a1a1a",
        "card_bg": "#202020",
        "recip_card_bg": "#261c10",
        "subcard_bg": "#181818",
        "input_bg": "#121212",
        "item_bg": "#262626",
        "item_selected_bg": "#332b14",
        "footer_bg": "#1a1a1a",
        "log_bg": "#0d0d0d",
        "border": "#383838",
        "input_border": "#525252",
        "text_primary": "#fafafa",
        "text_secondary": "#a3a3a3",
        "text_checkbox": "#e5e5e5",
        "pvz_addr": "#facc15",
        "accents": {
            "order": "#eab308",
            "sender": "#38bdf8",
            "recip": "#ff8c00",
            "goods": "#c084fc",
            "ship": "#22c55e",
            "comment": "#f87171",
        },
    },
    "Чёрное золото": {
        "mode": ft.ThemeMode.DARK,
        "bold_ui": False,
        "page_bg": "#050505",
        "sidebar_bg": "#0a0a0a",
        "card_bg": "#101010",
        "recip_card_bg": "#1c1306",
        "subcard_bg": "#080808",
        "input_bg": "#050505",
        "item_bg": "#141414",
        "item_selected_bg": "#241d08",
        "footer_bg": "#0a0a0a",
        "log_bg": "#030303",
        "border": "#3b2f10",
        "input_border": "#5c4818",
        "text_primary": "#fffbeb",
        "text_secondary": "#d4af37",
        "text_checkbox": "#fef3c7",
        "pvz_addr": "#facc15",
        "accents": {
            "order": "#f5c542",
            "sender": "#38bdf8",
            "recip": "#ff8c00",
            "goods": "#d4af37",
            "ship": "#34d399",
            "comment": "#f87171",
        },
    },
    "Тёплый песок": {
        "mode": ft.ThemeMode.LIGHT,
        "bold_ui": False,
        "page_bg": "#f5f0e6",
        "sidebar_bg": "#fbf8f1",
        "card_bg": "#fffdf9",
        "recip_card_bg": "#fff3e0",
        "subcard_bg": "#f7f2e7",
        "input_bg": "#ffffff",
        "item_bg": "#f7f2e7",
        "item_selected_bg": "#dcfce7",
        "footer_bg": "#fbf8f1",
        "log_bg": "#efe8d8",
        "border": "#d6ccb8",
        "input_border": "#b5a890",
        "text_primary": "#292524",
        "text_secondary": "#57534e",
        "text_checkbox": "#292524",
        "pvz_addr": "#9a3412",
        "accents": {
            "order": "#0369a1",
            "sender": "#1d4ed8",
            "recip": "#ea580c",
            "goods": "#6d28d9",
            "ship": "#047857",
            "comment": "#be123c",
        },
    },
}

TARIFF_OPTIONS = [
    "Посылка дверь-склад",
    "СДЭК Документы дверь-склад",
    "Экспресс дверь-склад",
    "Экспресс дверь-дверь",
    "Экспресс склад-склад",
    "Экспресс склад-дверь",
    "Супер-экспресс до 18 дверь-склад",
    "Супер-экспресс до 16 дверь-склад",
    "Магистральный экспресс дверь-склад",
]

RU_WEEKDAYS = [
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
]


def _normalize_recipient(item: dict) -> dict:
    """
    Приводит запись получателя к формату с двумя отдельными полями: company и fio.
    Для ЮР. ЛИЦО: если ФИО не указано — подставляет название фирмы в оба поля.
    """
    r = dict(item)
    rec_type = (r.get("recipient_type") or "ФИЗ. ЛИЦО").strip()
    raw_name = (r.get("name") or "").strip()
    company = (r.get("company") or "").strip()
    fio = (r.get("fio") or "").strip()

    if rec_type == "ЮР. ЛИЦО":
        if not company and not fio:
            m = re.match(r"^(.*?)\s*\(([^()]+)\)\s*$", raw_name)
            if m:
                company = m.group(1).strip()
                fio = m.group(2).strip()
            else:
                company = raw_name
                fio = raw_name
        elif company and not fio:
            fio = company
        elif fio and not company:
            company = fio
        display_name = company or fio or raw_name
    else:
        if not fio:
            fio = raw_name
        display_name = fio or company or raw_name

    r["recipient_type"] = rec_type
    r["company"] = company
    r["fio"] = fio
    r["name"] = display_name
    r["template"] = display_name
    return r


def _entry_day_key(h: dict) -> str:
    """Извлекает дату DD.MM.YYYY из записи истории (по времени создания или дате забора)."""
    created = (h.get("created_at") or "").strip()
    m = re.search(r"(\d{2}\.\d{2}\.\d{4})", created)
    if m:
        return m.group(1)
    d = (h.get("date") or "").strip()
    m2 = re.search(r"(\d{2}\.\d{2}\.\d{4})", d)
    if m2:
        return m2.group(1)
    return datetime.date.today().strftime("%d.%m.%Y")


def _format_day_title(day_str: str, count: int) -> str:
    try:
        dt = datetime.datetime.strptime(day_str, "%d.%m.%Y").date()
        wd = RU_WEEKDAYS[dt.weekday()]
        return f"{wd}, {day_str}  ({count} шт.)"
    except Exception:
        return f"{day_str}  ({count} шт.)"


def _format_track_line(h: dict) -> str:
    rec = (h.get("recipient") or "").strip()
    track = (h.get("track") or "").strip()
    return f"{rec} {track}".strip() if track else rec


def main(page: ft.Page):
    page.title = "Электроконнект — СДЭК (Выписка накладных)"
    page.padding = 0
    page.window.width = 1380
    page.window.height = 880
    page.window.min_width = 1120
    page.window.min_height = 700

    current_theme_name = "Графит и золото"

    def th():
        return THEMES[current_theme_name]

    def _w_input(t):
        return ft.FontWeight.BOLD if t.get("bold_ui") else ft.FontWeight.W_500

    def _w_label(t):
        return ft.FontWeight.BOLD if t.get("bold_ui") else ft.FontWeight.W_600

    def _w_sub(t):
        return ft.FontWeight.W_700 if t.get("bold_ui") else ft.FontWeight.NORMAL

    page.theme_mode = th()["mode"]
    page.bgcolor = th()["page_bg"]

    raw_recipients = load_recipients()
    recipients = [_normalize_recipient(r) for r in raw_recipients]
    if any(r.get("company") is None or r.get("fio") is None for r in raw_recipients):
        save_recipients(recipients)

    loaded_pvz: list[dict] = []
    pvz_load_seq = 0
    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)

    order_queue: queue.Queue = queue.Queue()
    queue_state = {"active": None, "pending": 0}
    queue_lock = threading.Lock()

    themed_inputs: list[tuple[ft.Control, str]] = []
    themed_checkboxes: list[tuple[ft.Checkbox, str]] = []
    themed_section_cards: list[tuple[ft.Container, ft.Icon, ft.Text, str, bool]] = []
    themed_sub_cards: list[tuple[ft.Container, ft.Icon, ft.Text, str]] = []
    themed_primary_texts: list[ft.Text] = []
    themed_secondary_texts: list[ft.Text] = []
    themed_accent_texts: list[tuple[ft.Text, str]] = []
    themed_dividers: list[ft.Divider] = []

    def copy_to_clipboard(text: str, toast_msg: str):
        if not text:
            return
        page.set_clipboard(text)
        page.open(
            ft.SnackBar(
                content=ft.Text(toast_msg, color="#ffffff", weight=ft.FontWeight.BOLD),
                bgcolor="#059669",
                duration=2000,
            )
        )

    def confirm_clear_history(_=None):
        def close_dlg(_=None):
            page.close(dlg)

        def do_clear(_=None):
            try:
                with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
            except Exception:
                pass
            page.close(dlg)
            refresh_tracks()
            refresh_history()
            add_log("Треки и история очищены.")
            page.open(
                ft.SnackBar(
                    content=ft.Text("Треки и история очищены", color="#ffffff", weight=ft.FontWeight.BOLD),
                    bgcolor="#dc2626",
                    duration=2000,
                )
            )

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Очистить треки и историю?", weight=ft.FontWeight.BOLD),
            content=ft.Text("Все записи во вкладках «Треки» и «История» будут удалены. Продолжить?"),
            actions=[
                ft.TextButton("Отмена", on_click=close_dlg),
                ft.ElevatedButton(
                    "Очистить",
                    icon=ft.icons.DELETE_FOREVER,
                    bgcolor="#dc2626",
                    color="#ffffff",
                    on_click=do_clear,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.open(dlg)

    def styled_tf(
        label: str,
        value: str = "",
        accent_key: str = "order",
        expand=None,
        width=None,
        password: bool = False,
        can_reveal_password: bool = False,
        multiline: bool = False,
        min_lines: int = 1,
        max_lines: int = 1,
        hint_text: str | None = None,
        prefix_icon=None,
        suffix=None,
    ) -> ft.TextField:
        t = th()
        accent = t["accents"][accent_key]
        ctrl = ft.TextField(
            label=label,
            value=value,
            hint_text=hint_text,
            prefix_icon=prefix_icon,
            suffix=suffix,
            password=password,
            can_reveal_password=can_reveal_password,
            multiline=multiline,
            min_lines=min_lines,
            max_lines=max_lines,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=13),
            expand=expand,
            width=width,
            filled=True,
            fill_color=t["input_bg"],
            border_color=t["input_border"],
            focused_border_color=accent,
            border_radius=8,
            label_style=ft.TextStyle(color=accent, weight=_w_label(t), size=13),
            text_style=ft.TextStyle(color=t["text_primary"], weight=_w_input(t), size=15),
            hint_style=ft.TextStyle(color=t["text_secondary"], weight=_w_sub(t), size=13),
        )
        themed_inputs.append((ctrl, accent_key))
        return ctrl

    def styled_dd(
        label: str,
        value: str,
        options: list[str],
        accent_key: str = "order",
        expand=None,
        width=None,
    ) -> ft.Dropdown:
        t = th()
        accent = t["accents"][accent_key]
        ctrl = ft.Dropdown(
            label=label,
            value=value,
            options=[ft.dropdown.Option(x) for x in options],
            content_padding=ft.padding.symmetric(horizontal=12, vertical=12),
            expand=expand,
            width=width,
            filled=True,
            fill_color=t["input_bg"],
            border_color=t["input_border"],
            focused_border_color=accent,
            border_radius=8,
            label_style=ft.TextStyle(color=accent, weight=_w_label(t), size=13),
            text_style=ft.TextStyle(color=t["text_primary"], weight=_w_input(t), size=15),
        )
        themed_inputs.append((ctrl, accent_key))
        return ctrl

    def styled_cb(label: str, value: bool, accent_key: str, size: int = 13) -> ft.Checkbox:
        t = th()
        cb = ft.Checkbox(
            label=label,
            value=value,
            active_color=t["accents"][accent_key],
            label_style=ft.TextStyle(color=t["text_checkbox"], weight=_w_sub(t), size=size),
        )
        themed_checkboxes.append((cb, accent_key))
        return cb

    # --- 1. О ЗАКАЗЕ И ДОСТУП ---
    tf_login = styled_tf("Логин СДЭК", "Msk001", accent_key="order", expand=1)
    tf_password = styled_tf(
        "Пароль СДЭК",
        "#Ljcneg2026",
        accent_key="order",
        password=True,
        can_reveal_password=True,
        expand=1,
    )
    dd_role = styled_dd(
        "Кем я являюсь",
        "ОТПРАВИТЕЛЕМ",
        ["ОТПРАВИТЕЛЕМ", "ПОЛУЧАТЕЛЕМ", "ТРЕТЬЕЙ СТОРОНОЙ"],
        accent_key="order",
        expand=1,
    )
    dd_payer = styled_dd(
        "Оплата",
        "ПО ДОГОВОРУ",
        ["ПО ДОГОВОРУ", "ОТПРАВИТЕЛЕМ", "ПОЛУЧАТЕЛЕМ"],
        accent_key="order",
        expand=1,
    )
    tf_cost_center = styled_tf("Центр затрат", "Москва", accent_key="order", expand=1)
    tf_city_from = styled_tf("Город отправителя", "Москва, Москва, Россия", accent_key="order", expand=1)
    tf_city_to = styled_tf("Город получателя", "", accent_key="order", expand=1)

    # --- 2. ОТПРАВИТЕЛЬ ---
    tf_sender_company = styled_tf("Компания (ИНН 5408154542)", '"ЭЛЕКТРОКОННЕКТ"', accent_key="sender", expand=1)
    tf_sender_fio = styled_tf("ФИО отправителя", "Крылова Людмила Борисовна", accent_key="sender", expand=1)
    tf_sender_phone = styled_tf("Телефон отправителя", "+7 916 195 36 94", accent_key="sender", expand=1)

    # --- 3. ПОЛУЧАТЕЛЬ ---
    dd_rec_type = styled_dd("Тип получателя", "ФИЗ. ЛИЦО", ["ФИЗ. ЛИЦО", "ЮР. ЛИЦО"], accent_key="recip", expand=1)
    tf_rec_company = styled_tf(
        "Фирма / Компания",
        "",
        hint_text='Например: ООО "Замоскворечье"',
        accent_key="recip",
        expand=2,
    )
    tf_rec_fio = styled_tf(
        "ФИО получателя",
        "",
        hint_text="Если фамилии нет — подставится фирма",
        accent_key="recip",
        expand=2,
    )
    tf_rec_phone = styled_tf("Телефон получателя", "", accent_key="recip", expand=1)
    tf_rec_email = styled_tf("Электронная почта", "", accent_key="recip", expand=1)

    # --- 4. ТОВАРЫ, ТАРИФ И ДОП. УСЛУГИ ---
    tf_weight = styled_tf("Вес, кг", "0.5", accent_key="goods", expand=1)
    tf_length = styled_tf("Длина, см", "10", accent_key="goods", expand=1)
    tf_width = styled_tf("Ширина, см", "5", accent_key="goods", expand=1)
    tf_height = styled_tf("Высота, см", "2", accent_key="goods", expand=1)
    tf_desc = styled_tf("Описание груза", "ПЛАТЫ", accent_key="goods", expand=2)

    dd_pickup_from = styled_dd(
        "Откуда",
        "КУРЬЕР ЗАБЕРЁТ ПО АДРЕСУ",
        ["КУРЬЕР ЗАБЕРЁТ ПО АДРЕСУ"],
        accent_key="goods",
        expand=1,
    )
    dd_delivery_to = styled_dd(
        "Куда доставить",
        "В ПВЗ",
        ["В ПВЗ"],
        accent_key="goods",
        expand=1,
    )
    dd_tariff = styled_dd("Тариф", "Экспресс дверь-склад", TARIFF_OPTIONS, accent_key="goods", expand=2)
    cb_insurance = styled_cb("Дополнительный сбор за объявленную стоимость", True, "goods")
    tf_declared = styled_tf("Объявленная стоимость, ₽", "3000", accent_key="goods", width=215)

    # --- 5. ИНФОРМАЦИЯ ОБ ОТПРАВЛЕНИИ ---
    tf_pickup_address = styled_tf("Адрес забора курьером", "Сущёвская, 21, офис 426", accent_key="ship", expand=2)
    tf_courier_comment = styled_tf("Комментарий для курьера", "", accent_key="ship", expand=1)
    tf_pickup_date = styled_tf("Дата забора", today.strftime("%d.%m.%Y"), accent_key="ship", width=160)
    tf_time_from = styled_tf("Забор с", "12:00", accent_key="ship", width=110)
    tf_time_to = styled_tf("Забор до", "15:00", accent_key="ship", width=110)

    cb_attorney = styled_cb("Курьеру необходима доверенность", False, "ship")
    cb_id_doc = styled_cb("Курьеру необходим документ удостоверяющий личность", False, "ship")

    tf_pvz_code = styled_tf("Код ПВЗ", "", accent_key="ship", width=135)
    tf_pvz_address = styled_tf("Адрес ПВЗ (или адрес доставки)", "", accent_key="ship", expand=True)

    def clear_pvz_filter(_=None):
        tf_pvz_search.value = ""
        render_pvz_list()

    tf_pvz_search = styled_tf(
        label="Фильтр списка ПВЗ",
        hint_text="Введи улицу, номер дома или код ПВЗ...",
        prefix_icon=ft.icons.SEARCH,
        suffix=ft.IconButton(
            icon=ft.icons.CLOSE,
            icon_size=16,
            icon_color="#94a3b8",
            tooltip="Показать все пункты города",
            on_click=clear_pvz_filter,
        ),
        accent_key="ship",
        expand=True,
    )
    dd_pvz_type_filter = styled_dd("Тип пункта", "Пункт выдачи", ["Все", "Пункт выдачи", "Постамат"], accent_key="ship", width=170)
    pvz_status_text = ft.Text(
        "При выборе клиента из базы ПВЗ города подгружаются автоматически.",
        size=12,
        color=th()["text_secondary"],
        weight=_w_sub(th()),
    )
    themed_secondary_texts.append(pvz_status_text)
    pvz_list_view = ft.ListView(height=175, spacing=4)

    # --- 6. КОММЕНТАРИЙ К ЗАКАЗУ ---
    tf_order_comment = styled_tf(
        "Комментарий к заказу",
        "УПД",
        accent_key="comment",
        multiline=True,
        min_lines=2,
        max_lines=3,
    )

    cb_auto_save = styled_cb(
        "Если получателя нет в базе — автоматически сохранять его в справочник при создании заказа",
        True,
        "recip",
        size=12,
    )

    log_view = ft.ListView(height=72, spacing=2, auto_scroll=True)

    def add_log(msg: str):
        t = th()
        log_view.controls.append(ft.Text(msg, size=12, color=t["text_primary"], weight=_w_sub(t)))
        if len(log_view.controls) > 120:
            log_view.controls.pop(0)
        page.update()

    def set_date(d: datetime.date):
        tf_pickup_date.value = d.strftime("%d.%m.%Y")
        page.update()

    def set_interval(t1: str, t2: str):
        tf_time_from.value = t1
        tf_time_to.value = t2
        page.update()

    # --- ЛОГИКА ЗАГРУЗКИ, АВТОПОДБОРА И ВЫБОРА ПВЗ ---
    STOP_WORDS = {"ул", "улица", "д", "дом", "пр", "проспект", "пр-т", "мкр", "корп", "к", "пом", "оф", "стр", "с"}

    def _norm_search_text(text: str) -> str:
        return re.sub(r"[^a-zа-я0-9]+", " ", (text or "").lower().replace("ё", "е")).strip()

    def _extract_tokens(text: str) -> list[str]:
        return [tok for tok in _norm_search_text(text).split() if tok not in STOP_WORDS]

    def _find_best_pvz(items: list[dict], target_code: str, target_addr: str) -> dict | None:
        pvz_only = [it for it in items if it.get("type") != "Постамат"] or items

        code_low = (target_code or "").strip().lower()
        if code_low:
            for it in pvz_only:
                if (it.get("code") or "").strip().lower() == code_low:
                    return it

        tokens = _extract_tokens(target_addr)
        if not tokens:
            return None

        best_item = None
        best_score = 0
        for it in pvz_only:
            hay = _norm_search_text(f"{it.get('code', '')} {it.get('address', '')}")
            if all(tok in hay for tok in tokens):
                return it
            hits = sum(1 for tok in tokens if tok in hay)
            if hits > best_score:
                best_score = hits
                best_item = it

        if best_item and best_score >= max(1, len(tokens) - 1):
            return best_item
        return None

    def select_pvz(item: dict):
        tf_pvz_code.value = item.get("code", "")
        tf_pvz_address.value = item.get("address", "")
        dd_delivery_to.value = "В ПВЗ"
        add_log(f"Выбран ПВЗ: {item.get('code')} — {item.get('address')}")
        render_pvz_list()

    def render_pvz_list(_=None):
        t = th()
        tokens = _extract_tokens(tf_pvz_search.value or "")
        t_filter = dd_pvz_type_filter.value
        selected_code = (tf_pvz_code.value or "").strip().lower()
        pvz_list_view.controls.clear()

        matched_count = 0
        for item in loaded_pvz:
            if t_filter != "Все" and item.get("type") != t_filter:
                continue
            haystack = _norm_search_text(f"{item.get('code', '')} {item.get('address', '')} {item.get('city', '')}")
            if tokens and not all(tok in haystack for tok in tokens):
                continue

            matched_count += 1
            is_postamat = item.get("type") == "Постамат"
            badge_color = t["accents"]["order"] if is_postamat else t["accents"]["ship"]
            is_selected = bool(selected_code and (item.get("code") or "").strip().lower() == selected_code)

            pvz_list_view.controls.append(
                ft.Container(
                    bgcolor=t["item_selected_bg"] if is_selected else t["item_bg"],
                    border=ft.border.all(2 if is_selected else 1, badge_color if is_selected else t["border"]),
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=10, vertical=6),
                    on_click=lambda e, it=item: select_pvz(it),
                    content=ft.Row(
                        [
                            ft.Container(width=8, height=8, border_radius=4, bgcolor=badge_color),
                            ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Container(
                                                bgcolor=t["input_bg"],
                                                border=ft.border.all(1, badge_color),
                                                border_radius=4,
                                                padding=ft.padding.symmetric(horizontal=6, vertical=1),
                                                content=ft.Text(
                                                    item.get("code", "") or "ПВЗ",
                                                    size=11,
                                                    weight=ft.FontWeight.BOLD,
                                                    color=badge_color,
                                                ),
                                            ),
                                            ft.Text(
                                                item.get("type", ""),
                                                size=11,
                                                weight=_w_label(t),
                                                color=badge_color,
                                            ),
                                            ft.Text(
                                                "✓ ВЫБРАН" if is_selected else "",
                                                size=11,
                                                weight=ft.FontWeight.BOLD,
                                                color=badge_color,
                                            ),
                                            ft.Text(
                                                f"• {item.get('work_time', '')}" if item.get("work_time") else "",
                                                size=11,
                                                weight=_w_sub(t),
                                                color=t["text_secondary"],
                                            ),
                                        ],
                                        spacing=6,
                                        wrap=True,
                                    ),
                                    ft.Text(
                                        item.get("address", ""),
                                        size=13,
                                        weight=ft.FontWeight.BOLD,
                                        color=t["pvz_addr"],
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.Icon(
                                ft.icons.CHECK_CIRCLE if is_selected else ft.icons.CHECK_CIRCLE_OUTLINE,
                                size=18,
                                color=badge_color,
                            ),
                        ],
                        spacing=8,
                    ),
                )
            )

        if loaded_pvz and matched_count == 0:
            pvz_list_view.controls.append(
                ft.Container(
                    padding=10,
                    content=ft.Text(
                        "По фильтру ничего не найдено — нажми × в строке фильтра, чтобы показать все пункты города.",
                        size=12,
                        weight=_w_sub(t),
                        color=t["accents"]["recip"],
                    ),
                )
            )
        page.update()

    btn_load_pvz = ft.ElevatedButton(
        "Загрузить ПВЗ из интернета",
        icon=ft.icons.CLOUD_DOWNLOAD,
        bgcolor="#0f2922",
        color="#34d399",
        style=ft.ButtonStyle(
            side=ft.BorderSide(1, "#34d399"),
            shape=ft.RoundedRectangleBorder(radius=8),
        ),
    )

    def start_pvz_fetch(city: str, target_code: str = "", target_addr: str = "", auto_select: bool = False):
        nonlocal pvz_load_seq
        pvz_load_seq += 1
        my_seq = pvz_load_seq

        city_clean = (city or "").strip()
        if not city_clean:
            return

        btn_load_pvz.disabled = True
        pvz_status_text.value = f"Загружаю пункты выдачи для «{city_clean}»..."
        page.update()

        def worker():
            nonlocal loaded_pvz
            items, msg = fetch_cdek_pvz(city_clean)
            if my_seq != pvz_load_seq:
                return
            loaded_pvz = items
            btn_load_pvz.disabled = False

            if auto_select and items and (target_code or target_addr):
                best = _find_best_pvz(items, target_code, target_addr)
                if best:
                    tf_pvz_code.value = best.get("code", "")
                    tf_pvz_address.value = best.get("address", "")
                    tf_pvz_search.value = best.get("code", "") or best.get("address", "")
                    dd_delivery_to.value = "В ПВЗ"
                    pvz_status_text.value = f"{msg} • Автовыбран: {best.get('code')} ({best.get('address')})"
                else:
                    tf_pvz_search.value = ""
                    pvz_status_text.value = f"{msg} • Точный ПВЗ не совпал, выбери из списка."
            else:
                pvz_status_text.value = msg

            render_pvz_list()

        threading.Thread(target=worker, daemon=True).start()

    def on_load_pvz_click(_):
        tf_pvz_search.value = ""
        dd_pvz_type_filter.value = "Пункт выдачи"
        start_pvz_fetch(tf_city_to.value, auto_select=False)

    btn_load_pvz.on_click = on_load_pvz_click
    tf_pvz_search.on_change = render_pvz_list
    dd_pvz_type_filter.on_change = render_pvz_list

    # --- СПРАВОЧНИК ПОЛУЧАТЕЛЕЙ (ПРАВАЯ ПАНЕЛЬ) + РЕДАКТИРОВАНИЕ И БЕЗОПАСНОЕ УДАЛЕНИЕ ---
    tf_search = styled_tf(
        label="Поиск в базе",
        hint_text="Фирма, ФИО, телефон или город...",
        prefix_icon=ft.icons.SEARCH,
        accent_key="recip",
    )
    recipients_list = ft.ListView(expand=True, spacing=7)

    def apply_recipient(item: dict):
        nonlocal loaded_pvz
        norm = _normalize_recipient(item)
        dd_rec_type.value = norm.get("recipient_type", "ФИЗ. ЛИЦО")
        tf_rec_company.value = norm.get("company", "")
        tf_rec_fio.value = norm.get("fio", "")
        tf_rec_phone.value = norm.get("phone", "")
        tf_rec_email.value = norm.get("email", "")
        tf_city_to.value = norm.get("city_to", "")
        tf_pvz_code.value = norm.get("pvz_code", "")
        tf_pvz_address.value = norm.get("pvz_address", "")
        dd_delivery_to.value = "В ПВЗ"
        tariff = norm.get("tariff", "Экспресс дверь-склад")
        if any(opt.key == tariff for opt in dd_tariff.options):
            dd_tariff.value = tariff
        else:
            dd_tariff.value = "Экспресс дверь-склад"

        if norm.get("time_from"):
            tf_time_from.value = norm["time_from"]
        if norm.get("time_to"):
            tf_time_to.value = norm["time_to"]

        tf_pvz_search.value = ""
        dd_pvz_type_filter.value = "Пункт выдачи"
        loaded_pvz = []
        pvz_list_view.controls.clear()
        add_log(f"Загружен получатель: {norm.get('name')} — подтягиваю ПВЗ...")
        page.update()

        if norm.get("city_to"):
            start_pvz_fetch(
                city=norm.get("city_to", ""),
                target_code=norm.get("pvz_code", ""),
                target_addr=norm.get("pvz_address", ""),
                auto_select=True,
            )

    def open_edit_recipient_dialog(item: dict):
        norm = _normalize_recipient(item)
        orig_name = norm.get("name", "")
        ed_type = ft.Dropdown(
            label="Тип получателя",
            value=norm.get("recipient_type", "ФИЗ. ЛИЦО"),
            options=[ft.dropdown.Option("ФИЗ. ЛИЦО"), ft.dropdown.Option("ЮР. ЛИЦО")],
            dense=True,
        )
        ed_company = ft.TextField(
            label="Фирма / Компания",
            value=norm.get("company", ""),
            hint_text='Например: ООО "Замоскворечье"',
            dense=True,
        )
        ed_fio = ft.TextField(
            label="ФИО получателя",
            value=norm.get("fio", ""),
            hint_text="Если фамилии нет — подставится фирма",
            dense=True,
        )
        ed_phone = ft.TextField(label="Телефон", value=norm.get("phone", ""), dense=True)
        ed_email = ft.TextField(label="Электронная почта", value=norm.get("email", ""), dense=True)
        ed_city = ft.TextField(label="Город получателя", value=norm.get("city_to", ""), dense=True)
        ed_pvz_code = ft.TextField(label="Код ПВЗ", value=norm.get("pvz_code", ""), dense=True, width=140)
        ed_pvz_addr = ft.TextField(label="Адрес ПВЗ", value=norm.get("pvz_address", ""), dense=True, expand=True)
        ed_time_from = ft.TextField(label="Забор с", value=norm.get("time_from", "12:00"), dense=True, width=120)
        ed_time_to = ft.TextField(label="Забор до", value=norm.get("time_to", "15:00"), dense=True, width=120)
        cur_tariff = norm.get("tariff", "Экспресс дверь-склад")
        if cur_tariff not in TARIFF_OPTIONS:
            cur_tariff = "Экспресс дверь-склад"
        ed_tariff = ft.Dropdown(
            label="Тариф",
            value=cur_tariff,
            options=[ft.dropdown.Option(x) for x in TARIFF_OPTIONS],
            dense=True,
        )

        def close_dlg(_=None):
            page.close(dlg)

        def delete_from_dlg(_):
            nonlocal recipients
            recipients = [r for r in recipients if r.get("name") != orig_name]
            save_recipients(recipients)
            refresh_recipients()
            add_log(f"Удалён получатель из базы: {orig_name}")
            page.close(dlg)

        def save_dlg(_):
            comp_val = (ed_company.value or "").strip()
            fio_val = (ed_fio.value or "").strip()
            if not comp_val and not fio_val:
                return
            updated = _normalize_recipient(
                {
                    "recipient_type": ed_type.value,
                    "company": comp_val,
                    "fio": fio_val,
                    "phone": (ed_phone.value or "").strip(),
                    "email": (ed_email.value or "").strip(),
                    "city_to": (ed_city.value or "").strip(),
                    "pvz_code": (ed_pvz_code.value or "").strip(),
                    "pvz_address": (ed_pvz_addr.value or "").strip(),
                    "time_from": (ed_time_from.value or "12:00").strip(),
                    "time_to": (ed_time_to.value or "15:00").strip(),
                    "delivery_to": "В ПВЗ",
                    "tariff": ed_tariff.value,
                }
            )
            nonlocal recipients
            replaced = False
            for idx, r in enumerate(recipients):
                if r.get("name", "") == orig_name:
                    recipients[idx] = updated
                    replaced = True
                    break
            if not replaced:
                recipients.insert(0, updated)
            save_recipients(recipients)
            refresh_recipients()

            cur_active = (tf_rec_company.value or tf_rec_fio.value or "").strip().lower()
            if cur_active == orig_name.strip().lower():
                apply_recipient(updated)

            add_log(f"Обновлён получатель в базе: {updated['name']}")
            page.close(dlg)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Редактировать получателя", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=520,
                content=ft.Column(
                    [
                        ed_type,
                        ed_company,
                        ed_fio,
                        ft.Row([ed_phone, ed_email]),
                        ed_city,
                        ft.Row([ed_pvz_code, ed_pvz_addr]),
                        ft.Row([ed_time_from, ed_time_to, ed_tariff]),
                    ],
                    tight=True,
                    spacing=10,
                ),
            ),
            actions=[
                ft.TextButton(
                    "Удалить клиента",
                    icon=ft.icons.DELETE_OUTLINE,
                    style=ft.ButtonStyle(color="#ef4444"),
                    on_click=delete_from_dlg,
                ),
                ft.Container(expand=True),
                ft.TextButton("Отмена", on_click=close_dlg),
                ft.ElevatedButton("Сохранить", icon=ft.icons.SAVE, bgcolor="#10b981", color="#052e16", on_click=save_dlg),
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        page.open(dlg)

    def refresh_recipients(_=None):
        t = th()
        query = (tf_search.value or "").strip().lower()
        recipients_list.controls.clear()
        for item in recipients:
            haystack = " ".join(
                [
                    item.get("name", ""),
                    item.get("company", ""),
                    item.get("fio", ""),
                    item.get("phone", ""),
                    item.get("city_to", ""),
                ]
            ).lower()
            if query and query not in haystack:
                continue

            comp = (item.get("company") or "").strip()
            fio = (item.get("fio") or "").strip()
            city = (item.get("city_to") or "").strip()
            title_text = comp or fio or item.get("name", "")
            if comp and fio and comp.lower() != fio.lower():
                sub_text = f"{fio} • {city}" if city else fio
            else:
                sub_text = city

            is_org = item.get("recipient_type") == "ЮР. ЛИЦО"
            recipients_list.controls.append(
                ft.Container(
                    bgcolor=t["item_bg"],
                    border=ft.border.all(1, t["border"]),
                    border_radius=9,
                    padding=ft.padding.symmetric(horizontal=12, vertical=10),
                    content=ft.Row(
                        [
                            ft.Icon(
                                ft.icons.BUSINESS if is_org else ft.icons.PERSON,
                                size=19,
                                color=t["accents"]["recip"],
                            ),
                            ft.Column(
                                [
                                    ft.Text(
                                        title_text,
                                        size=14,
                                        weight=_w_label(t),
                                        color=t["text_primary"],
                                    ),
                                    ft.Text(
                                        sub_text,
                                        size=12,
                                        weight=_w_sub(t),
                                        color=t["text_secondary"],
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.icons.EDIT,
                                icon_size=18,
                                icon_color=t["accents"]["order"],
                                tooltip="Редактировать / удалить получателя",
                                on_click=lambda e, it=item: open_edit_recipient_dialog(it),
                            ),
                        ],
                        spacing=6,
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    on_click=lambda e, it=item: apply_recipient(it),
                )
            )
        recipients_header.value = f"Справочник получателей ({len(recipients)})"
        page.update()

    def save_current_to_base(_=None, silent: bool = False):
        comp_val = tf_rec_company.value.strip()
        fio_val = tf_rec_fio.value.strip()
        if not comp_val and not fio_val:
            if not silent:
                add_log("Введи фирму или ФИО получателя, чтобы сохранить в базу.")
            return
        new_item = _normalize_recipient(
            {
                "recipient_type": dd_rec_type.value,
                "company": comp_val,
                "fio": fio_val,
                "phone": tf_rec_phone.value.strip(),
                "email": tf_rec_email.value.strip(),
                "city_to": tf_city_to.value.strip(),
                "pvz_code": tf_pvz_code.value.strip(),
                "pvz_address": tf_pvz_address.value.strip(),
                "time_from": tf_time_from.value.strip() or "12:00",
                "time_to": tf_time_to.value.strip() or "15:00",
                "delivery_to": "В ПВЗ",
                "tariff": dd_tariff.value,
            }
        )
        tf_rec_company.value = new_item["company"]
        tf_rec_fio.value = new_item["fio"]

        nonlocal recipients
        key_low = new_item["name"].strip().lower()
        recipients = [r for r in recipients if r.get("name", "").strip().lower() != key_low]
        recipients.insert(0, new_item)
        save_recipients(recipients)
        refresh_recipients()
        if not silent:
            add_log(f"Сохранено в справочник: {new_item['name']}")

    def clear_recipient_fields(_):
        nonlocal loaded_pvz
        tf_rec_company.value = ""
        tf_rec_fio.value = ""
        tf_rec_phone.value = ""
        tf_rec_email.value = ""
        tf_city_to.value = ""
        tf_pvz_code.value = ""
        tf_pvz_address.value = ""
        tf_pvz_search.value = ""
        loaded_pvz = []
        pvz_list_view.controls.clear()
        add_log("Поля получателя очищены — можно вводить нового клиента.")
        page.update()

    tf_search.on_change = refresh_recipients
    recipients_header = ft.Text(
        f"Справочник получателей ({len(recipients)})",
        size=15,
        weight=ft.FontWeight.BOLD,
        color=th()["accents"]["recip"],
    )
    themed_accent_texts.append((recipients_header, "recip"))

    # --- ЗАКРЕПЛЁННАЯ КНОПКА «СОЗДАТЬ ЗАКАЗ» + СЧЁТЧИК ОЧЕРЕДИ ---
    queue_badge_text = ft.Text("Очередь: 0 (свободно)", size=13, weight=ft.FontWeight.BOLD, color="#34d399")
    queue_badge = ft.Container(
        bgcolor="#0f2922",
        border=ft.border.all(1, "#10b981"),
        border_radius=10,
        padding=ft.padding.symmetric(horizontal=14, vertical=14),
        content=ft.Row(
            [
                ft.Icon(ft.icons.LAYERS, size=18, color="#34d399"),
                queue_badge_text,
            ],
            spacing=6,
        ),
    )

    btn_run = ft.ElevatedButton(
        text="СОЗДАТЬ ЗАКАЗ И РАСПЕЧАТАТЬ НАКЛАДНУЮ",
        icon=ft.icons.LOCAL_SHIPPING,
        bgcolor="#10b981",
        color="#052e16",
        height=52,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=10),
            text_style=ft.TextStyle(weight=ft.FontWeight.BOLD, size=15),
        ),
        expand=True,
    )

    def update_queue_badge():
        with queue_lock:
            active = queue_state["active"]
            pending = queue_state["pending"]
        if active:
            short_name = active[:22] + ("…" if len(active) > 22 else "")
            queue_badge_text.value = f"В работе: {short_name} | В очереди: {pending}"
            queue_badge.bgcolor = "#2a2210"
            queue_badge.border = ft.border.all(1, "#fbbf24")
            queue_badge_text.color = "#fbbf24"
        else:
            queue_badge_text.value = "Очередь: 0 (свободно)"
            queue_badge.bgcolor = "#0f2922"
            queue_badge.border = ft.border.all(1, "#10b981")
            queue_badge_text.color = "#34d399"
        page.update()

    def queue_worker_loop():
        while True:
            payload = order_queue.get()
            rec_label = payload.get("recipient_company") or payload.get("recipient_fio") or "Заказ"
            with queue_lock:
                queue_state["pending"] = max(0, queue_state["pending"] - 1)
                queue_state["active"] = rec_label
            update_queue_badge()
            add_log(f"=== Старт заказа: {rec_label} ({payload.get('city_to', '')}) ===")
            try:
                run_cdek_order(payload, add_log)
            except Exception as exc:
                add_log(f"[ОШИБКА {rec_label}]: {exc}")
            finally:
                with queue_lock:
                    queue_state["active"] = None
                refresh_history()
                refresh_tracks()
                update_queue_badge()
                order_queue.task_done()

    threading.Thread(target=queue_worker_loop, daemon=True).start()

    def on_run_click(_):
        rec_type = dd_rec_type.value
        rec_company = tf_rec_company.value.strip()
        rec_fio = tf_rec_fio.value.strip()

        if rec_type == "ЮР. ЛИЦО":
            if rec_company and not rec_fio:
                rec_fio = rec_company
            elif rec_fio and not rec_company:
                rec_company = rec_fio

        rec_key = (rec_company or rec_fio).strip()
        if cb_auto_save.value and rec_key:
            exists = any(r.get("name", "").strip().lower() == rec_key.lower() for r in recipients)
            if not exists:
                save_current_to_base(silent=True)

        order_payload = {
            "login": tf_login.value,
            "password": tf_password.value,
            "role": dd_role.value,
            "payer": dd_payer.value,
            "cost_center": tf_cost_center.value,
            "city_from": tf_city_from.value,
            "city_to": tf_city_to.value,
            "sender_fio": tf_sender_fio.value,
            "sender_phone": tf_sender_phone.value,
            "recipient_type": rec_type,
            "recipient_company": rec_company,
            "recipient_fio": rec_fio,
            "recipient_phone": tf_rec_phone.value,
            "recipient_email": tf_rec_email.value,
            "weight": tf_weight.value,
            "length": tf_length.value,
            "width": tf_width.value,
            "height": tf_height.value,
            "description": tf_desc.value,
            "pickup_from": "КУРЬЕР ЗАБЕРЁТ ПО АДРЕСУ",
            "delivery_to": "В ПВЗ",
            "tariff": dd_tariff.value,
            "use_insurance": cb_insurance.value,
            "declared_value": tf_declared.value,
            "pickup_address": tf_pickup_address.value,
            "courier_comment": tf_courier_comment.value,
            "pickup_date": tf_pickup_date.value,
            "time_from": tf_time_from.value,
            "time_to": tf_time_to.value,
            "need_attorney": cb_attorney.value,
            "need_id_doc": cb_id_doc.value,
            "pvz_code": tf_pvz_code.value,
            "pvz_address": tf_pvz_address.value,
            "order_comment": tf_order_comment.value,
        }

        with queue_lock:
            queue_state["pending"] += 1
            pos = queue_state["pending"]
        order_queue.put(order_payload)
        add_log(f"+ Добавлен в очередь (#{pos}): {rec_key or 'Без имени'} — {tf_city_to.value}")
        update_queue_badge()

    btn_run.on_click = on_run_click

    # --- КАРТОЧКИ СЕКЦИЙ ---
    def section_card(title: str, icon, accent_key: str, controls: list, highlight: bool = False):
        t = th()
        accent = t["accents"][accent_key]
        ic = ft.Icon(icon, color=accent, size=22 if highlight else 20)
        tx = ft.Text(title, size=16 if highlight else 15, weight=ft.FontWeight.BOLD, color=accent)
        if highlight:
            card_bg = t.get("recip_card_bg", t["card_bg"])
            card_border = ft.border.only(
                left=ft.BorderSide(6, accent),
                top=ft.BorderSide(1.5, accent),
                right=ft.BorderSide(1.5, accent),
                bottom=ft.BorderSide(1.5, accent),
            )
        else:
            card_bg = t["card_bg"]
            card_border = ft.border.only(
                left=ft.BorderSide(4, accent),
                top=ft.BorderSide(1, t["border"]),
                right=ft.BorderSide(1, t["border"]),
                bottom=ft.BorderSide(1, t["border"]),
            )
        box = ft.Container(
            bgcolor=card_bg,
            border_radius=12,
            border=card_border,
            padding=16,
            content=ft.Column([ft.Row([ic, tx], spacing=8), *controls], spacing=12),
        )
        themed_section_cards.append((box, ic, tx, accent_key, highlight))
        return box

    def sub_card(title: str, icon, accent_key: str, controls: list):
        t = th()
        accent = t["accents"][accent_key]
        ic = ft.Icon(icon, color=accent, size=17)
        tx = ft.Text(title, size=13, weight=ft.FontWeight.BOLD, color=accent)
        box = ft.Container(
            bgcolor=t["subcard_bg"],
            border_radius=10,
            border=ft.border.all(1, accent),
            padding=12,
            content=ft.Column([ft.Row([ic, tx], spacing=6), *controls], spacing=10),
        )
        themed_sub_cards.append((box, ic, tx, accent_key))
        return box

    # --- ШАПКА ---
    header_title = ft.Text('ООО «ЭЛЕКТРОКОННЕКТ» — СДЭК', size=18, weight=ft.FontWeight.BOLD, color=th()["text_primary"])
    header_subtitle = ft.Text(
        "ИНН 5408154542 • Очередь заказов • Всегда в ПВЗ • Автопечать 3 копий",
        size=12,
        weight=_w_sub(th()),
        color=th()["text_secondary"],
    )
    themed_primary_texts.append(header_title)
    themed_secondary_texts.append(header_subtitle)

    top_header_card = ft.Container(
        bgcolor=th()["card_bg"],
        border_radius=12,
        padding=14,
        border=ft.border.all(1, th()["border"]),
        content=ft.Row(
            [
                ft.Icon(ft.icons.LOCAL_SHIPPING, color="#10b981", size=30),
                ft.Column([header_title, header_subtitle], spacing=2, expand=True),
                ft.OutlinedButton("Новый клиент", icon=ft.icons.CLEAR_ALL, on_click=clear_recipient_fields),
                ft.ElevatedButton(
                    "Сохранить в базу",
                    icon=ft.icons.PERSON_ADD,
                    bgcolor="#2a2210",
                    color="#fbbf24",
                    style=ft.ButtonStyle(
                        side=ft.BorderSide(1, "#fbbf24"),
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                    on_click=save_current_to_base,
                ),
            ],
            spacing=8,
        ),
    )

    pvz_section_label = ft.Text(
        "Доставить в ПВЗ",
        size=13,
        weight=ft.FontWeight.BOLD,
        color=th()["accents"]["ship"],
    )
    themed_accent_texts.append((pvz_section_label, "ship"))

    pvz_divider = ft.Divider(height=1, color=th()["border"])
    themed_dividers.append(pvz_divider)

    pvz_box_container = ft.Container(
        bgcolor=th()["input_bg"],
        border_radius=8,
        padding=6,
        border=ft.border.all(1, th()["border"]),
        content=pvz_list_view,
    )

    # --- ВКЛАДКА 1: ОФОРМЛЕНИЕ ---
    scrollable_form = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        spacing=15,
        controls=[
            top_header_card,
            section_card(
                "1. О ЗАКАЗЕ И ДОСТУП",
                ft.icons.ASSIGNMENT,
                "order",
                [
                    sub_card("Доступ в личный кабинет lk.cdek.ru", ft.icons.LOCK_OPEN, "order", [ft.Row([tf_login, tf_password])]),
                    ft.Row([dd_role, dd_payer, tf_cost_center]),
                    ft.Row([tf_city_from, tf_city_to]),
                ],
            ),
            section_card(
                "2. ОТПРАВИТЕЛЬ",
                ft.icons.OUTBOX,
                "sender",
                [
                    ft.Row([tf_sender_company, tf_sender_fio, tf_sender_phone]),
                ],
            ),
            section_card(
                "3. ПОЛУЧАТЕЛЬ",
                ft.icons.MOVE_TO_INBOX,
                "recip",
                [
                    ft.Row([dd_rec_type, tf_rec_company, tf_rec_fio]),
                    ft.Row([tf_rec_phone, tf_rec_email]),
                ],
                highlight=True,
            ),
            section_card(
                "4. ТОВАРЫ, ТАРИФ И ДОП. УСЛУГИ",
                ft.icons.INVENTORY_2,
                "goods",
                [
                    ft.Row([tf_weight, tf_length, tf_width, tf_height, tf_desc]),
                    ft.Row([dd_pickup_from, dd_delivery_to, dd_tariff]),
                    ft.Row([cb_insurance, tf_declared]),
                ],
            ),
            section_card(
                "5. ИНФОРМАЦИЯ ОБ ОТПРАВЛЕНИИ (ЗАБОР И ПВЗ)",
                ft.icons.LOCATION_ON,
                "ship",
                [
                    ft.Row([tf_pickup_address, tf_courier_comment]),
                    ft.Row(
                        [
                            tf_pickup_date,
                            ft.OutlinedButton("Сегодня", on_click=lambda _: set_date(today)),
                            ft.OutlinedButton("Завтра", on_click=lambda _: set_date(tomorrow)),
                            tf_time_from,
                            tf_time_to,
                            ft.OutlinedButton("12:00-15:00", on_click=lambda _: set_interval("12:00", "15:00")),
                            ft.OutlinedButton("13:30-18:00", on_click=lambda _: set_interval("13:30", "18:00")),
                        ],
                        wrap=True,
                    ),
                    ft.Row([cb_attorney, cb_id_doc], wrap=True),
                    pvz_divider,
                    pvz_section_label,
                    ft.Row([tf_pvz_code, tf_pvz_address, btn_load_pvz]),
                    ft.Row([tf_pvz_search, dd_pvz_type_filter]),
                    pvz_status_text,
                    pvz_box_container,
                ],
            ),
            section_card(
                "6. КОММЕНТАРИЙ К ЗАКАЗУ",
                ft.icons.COMMENT,
                "comment",
                [tf_order_comment, cb_auto_save],
            ),
        ],
    )

    log_container = ft.Container(
        bgcolor=th()["log_bg"],
        border_radius=8,
        padding=6,
        content=log_view,
    )

    pinned_footer = ft.Container(
        bgcolor=th()["footer_bg"],
        border_radius=12,
        padding=12,
        border=ft.border.all(1, "#10b981"),
        content=ft.Column([ft.Row([btn_run, queue_badge], spacing=10), log_container], spacing=8),
    )

    order_tab = ft.Column(expand=True, spacing=10, controls=[scrollable_form, pinned_footer])

    # --- ВКЛАДКА 2: ТРЕКИ (СТАТИСТИКА ПО ДНЯМ С КОПИРОВАНИЕМ) ---
    tracks_title = ft.Text(
        "Треки ООО «ЭЛЕКТРОконнект» (0)",
        size=18,
        weight=ft.FontWeight.BOLD,
        color=th()["text_primary"],
    )
    themed_primary_texts.append(tracks_title)
    tracks_list = ft.ListView(expand=True, spacing=12)
    tracks_all_lines_ref = {"lines": []}

    def copy_all_tracks(_):
        lines = tracks_all_lines_ref["lines"]
        if not lines:
            return
        copy_to_clipboard("\n".join(lines), f"Скопированы все треки ({len(lines)} шт.)")

    btn_copy_all_tracks = ft.ElevatedButton(
        "КОПИРОВАТЬ ВСЁ",
        icon=ft.icons.CONTENT_COPY,
        bgcolor="#10b981",
        color="#052e16",
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=20),
            text_style=ft.TextStyle(weight=ft.FontWeight.BOLD, size=12),
        ),
        on_click=copy_all_tracks,
    )

    btn_clear_tracks = ft.OutlinedButton(
        "Очистить",
        icon=ft.icons.DELETE_OUTLINE,
        style=ft.ButtonStyle(
            color="#ef4444",
            side=ft.BorderSide(1, "#ef4444"),
            shape=ft.RoundedRectangleBorder(radius=20),
        ),
        on_click=confirm_clear_history,
    )

    def refresh_tracks(_=None):
        t = th()
        hist = load_history()
        tracks_list.controls.clear()

        grouped: dict[str, list[dict]] = {}
        for h in hist:
            day_k = _entry_day_key(h)
            grouped.setdefault(day_k, []).append(h)

        def _parse_day(ds: str):
            try:
                return datetime.datetime.strptime(ds, "%d.%m.%Y").date()
            except Exception:
                return datetime.date.min

        sorted_days = sorted(grouped.keys(), key=_parse_day, reverse=True)
        all_lines: list[str] = []
        total_cnt = 0

        for day_k in sorted_days:
            items = grouped[day_k]
            day_lines = [_format_track_line(it) for it in items if _format_track_line(it)]
            if not day_lines:
                continue
            total_cnt += len(day_lines)
            all_lines.extend(day_lines)

            rows_ui = []
            for line in day_lines:
                rows_ui.append(
                    ft.Row(
                        [
                            ft.Text(
                                line,
                                size=15,
                                weight=ft.FontWeight.BOLD,
                                color=t["text_primary"],
                                selectable=True,
                                expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.icons.CONTENT_COPY,
                                icon_size=17,
                                icon_color=t["text_secondary"],
                                tooltip="Копировать строку",
                                on_click=lambda e, ln=line: copy_to_clipboard(ln, f"Скопировано: {ln}"),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                )

            day_text_blob = "\n".join(day_lines)
            day_card = ft.Container(
                bgcolor=t["card_bg"],
                border=ft.border.all(1, t["border"]),
                border_radius=12,
                padding=ft.padding.symmetric(horizontal=16, vertical=14),
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.icons.CALENDAR_TODAY, size=15, color="#10b981"),
                                ft.Text(
                                    _format_day_title(day_k, len(day_lines)),
                                    size=15,
                                    weight=ft.FontWeight.BOLD,
                                    color=t["text_primary"],
                                    expand=True,
                                ),
                                ft.ElevatedButton(
                                    "КОПИРОВАТЬ ВСЁ ЗА ДЕНЬ",
                                    icon=ft.icons.CONTENT_COPY,
                                    bgcolor="#10b981",
                                    color="#052e16",
                                    height=34,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=20),
                                        text_style=ft.TextStyle(weight=ft.FontWeight.BOLD, size=12),
                                    ),
                                    on_click=lambda e, blob=day_text_blob, dk=day_k, n=len(day_lines): copy_to_clipboard(
                                        blob, f"Скопировано за {dk} ({n} шт.)"
                                    ),
                                ),
                            ],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Divider(height=1, color=t["border"]),
                        ft.Column(rows_ui, spacing=4),
                    ],
                    spacing=10,
                ),
            )
            tracks_list.controls.append(day_card)

        tracks_all_lines_ref["lines"] = all_lines
        tracks_title.value = f"Треки ООО «ЭЛЕКТРОконнект» ({total_cnt})"

        if total_cnt == 0:
            tracks_list.controls.append(
                ft.Container(
                    padding=20,
                    content=ft.Text(
                        "Пока нет оформленных отправлений. После создания заказа трек-номер появится здесь автоматически.",
                        size=14,
                        weight=_w_sub(t),
                        color=t["text_secondary"],
                    ),
                )
            )
        page.update()

    tracks_divider = ft.Divider(height=1, color=th()["border"])
    themed_dividers.append(tracks_divider)

    tracks_tab = ft.Column(
        expand=True,
        spacing=12,
        controls=[
            ft.Row(
                [
                    ft.Icon(ft.icons.RECEIPT_LONG, color="#10b981", size=24),
                    tracks_title,
                    ft.Container(expand=True),
                    btn_clear_tracks,
                    btn_copy_all_tracks,
                    ft.IconButton(
                        icon=ft.icons.REFRESH,
                        icon_color="#10b981",
                        tooltip="Обновить список треков",
                        on_click=refresh_tracks,
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            tracks_divider,
            tracks_list,
        ],
    )

    # --- ВКЛАДКА 3: ИСТОРИЯ ---
    history_list = ft.ListView(expand=True, spacing=10)
    history_title = ft.Text("История оформленных накладных", size=18, weight=ft.FontWeight.BOLD, color=th()["text_primary"])
    themed_primary_texts.append(history_title)

    btn_clear_history = ft.OutlinedButton(
        "Очистить историю",
        icon=ft.icons.DELETE_OUTLINE,
        style=ft.ButtonStyle(
            color="#ef4444",
            side=ft.BorderSide(1, "#ef4444"),
            shape=ft.RoundedRectangleBorder(radius=20),
        ),
        on_click=confirm_clear_history,
    )

    def refresh_history():
        t = th()
        history_list.controls.clear()
        items = load_history()
        if not items:
            history_list.controls.append(
                ft.Container(
                    padding=20,
                    content=ft.Text(
                        "История пуста.",
                        size=14,
                        weight=_w_sub(t),
                        color=t["text_secondary"],
                    ),
                )
            )
            return

        for h in items:
            track_part = f"Трек: {h['track']} • " if h.get("track") else ""
            history_list.controls.append(
                ft.Container(
                    bgcolor=t["card_bg"],
                    border=ft.border.all(1, t["border"]),
                    border_radius=10,
                    padding=14,
                    content=ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text(h.get("recipient", ""), size=15, weight=ft.FontWeight.BOLD, color=t["text_primary"]),
                                    ft.Text(
                                        f"{track_part}{h.get('city_to', '')} • ПВЗ: {h.get('pvz', '')} • Забор: {h.get('date', '')}",
                                        size=13,
                                        weight=_w_sub(t),
                                        color=t["text_secondary"],
                                    ),
                                ],
                                spacing=3,
                                expand=True,
                            ),
                            ft.Text(h.get("created_at", ""), size=12, weight=_w_sub(t), color=t["text_secondary"]),
                            ft.Icon(
                                ft.icons.PRINT if h.get("printed") else ft.icons.WARNING,
                                color="#10b981" if h.get("printed") else "#f59e0b",
                            ),
                        ]
                    ),
                )
            )

    history_divider = ft.Divider(height=1, color=th()["border"])
    themed_dividers.append(history_divider)

    history_tab = ft.Column(
        expand=True,
        spacing=12,
        controls=[
            ft.Row(
                [
                    ft.Icon(ft.icons.HISTORY, color="#10b981", size=24),
                    history_title,
                    ft.Container(expand=True),
                    btn_clear_history,
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            history_divider,
            history_list,
        ],
    )
    center_container = ft.Container(expand=True, padding=14, content=order_tab)

    def show_order(_):
        center_container.content = order_tab
        page.update()

    def show_tracks(_):
        refresh_tracks()
        center_container.content = tracks_tab
        page.update()

    def show_history(_):
        refresh_history()
        center_container.content = history_tab
        page.update()

    # --- ПЕРЕКЛЮЧАТЕЛЬ ТЕМ ---
    dd_theme = styled_dd("Тема оформления", current_theme_name, list(THEMES.keys()), accent_key="order")

    def on_theme_change(_):
        nonlocal current_theme_name
        current_theme_name = dd_theme.value
        t = th()

        page.theme_mode = t["mode"]
        page.bgcolor = t["page_bg"]

        left_sidebar.bgcolor = t["sidebar_bg"]
        left_sidebar.border = ft.border.only(right=ft.BorderSide(1, t["border"]))
        right_sidebar.bgcolor = t["sidebar_bg"]
        right_sidebar.border = ft.border.only(left=ft.BorderSide(1, t["border"]))

        top_header_card.bgcolor = t["card_bg"]
        top_header_card.border = ft.border.all(1, t["border"])
        pvz_box_container.bgcolor = t["input_bg"]
        pvz_box_container.border = ft.border.all(1, t["border"])
        pinned_footer.bgcolor = t["footer_bg"]
        log_container.bgcolor = t["log_bg"]

        for ctrl, akey in themed_inputs:
            acc = t["accents"][akey]
            ctrl.fill_color = t["input_bg"]
            ctrl.border_color = t["input_border"]
            ctrl.focused_border_color = acc
            ctrl.label_style = ft.TextStyle(color=acc, weight=_w_label(t), size=13)
            ctrl.text_style = ft.TextStyle(color=t["text_primary"], weight=_w_input(t), size=15)
            if hasattr(ctrl, "hint_style"):
                ctrl.hint_style = ft.TextStyle(color=t["text_secondary"], weight=_w_sub(t), size=13)

        for cb, akey in themed_checkboxes:
            cb.active_color = t["accents"][akey]
            cb.label_style = ft.TextStyle(
                color=t["text_checkbox"],
                weight=_w_sub(t),
                size=cb.label_style.size if cb.label_style else 13,
            )

        for box, ic, tx, akey, is_hl in themed_section_cards:
            acc = t["accents"][akey]
            if is_hl:
                box.bgcolor = t.get("recip_card_bg", t["card_bg"])
                box.border = ft.border.only(
                    left=ft.BorderSide(6, acc),
                    top=ft.BorderSide(1.5, acc),
                    right=ft.BorderSide(1.5, acc),
                    bottom=ft.BorderSide(1.5, acc),
                )
            else:
                box.bgcolor = t["card_bg"]
                box.border = ft.border.only(
                    left=ft.BorderSide(4, acc),
                    top=ft.BorderSide(1, t["border"]),
                    right=ft.BorderSide(1, t["border"]),
                    bottom=ft.BorderSide(1, t["border"]),
                )
            ic.color = acc
            tx.color = acc

        for box, ic, tx, akey in themed_sub_cards:
            acc = t["accents"][akey]
            box.bgcolor = t["subcard_bg"]
            box.border = ft.border.all(1, acc)
            ic.color = acc
            tx.color = acc

        for tx in themed_primary_texts:
            tx.color = t["text_primary"]
            tx.weight = ft.FontWeight.BOLD
        for tx in themed_secondary_texts:
            tx.color = t["text_secondary"]
            tx.weight = _w_sub(t)
        for tx, akey in themed_accent_texts:
            tx.color = t["accents"][akey]
        for dv in themed_dividers:
            dv.color = t["border"]
        for log_tx in log_view.controls:
            if isinstance(log_tx, ft.Text):
                log_tx.color = t["text_primary"]
                log_tx.weight = _w_sub(t)

        render_pvz_list()
        refresh_recipients()
        refresh_tracks()
        refresh_history()
        page.update()

    dd_theme.on_change = on_theme_change

    sumatra_ok = is_sumatra_ready()
    sumatra_badge = ft.Container(
        bgcolor="#0f2922" if sumatra_ok else "#2d1b1b",
        border=ft.border.all(1, "#10b981" if sumatra_ok else "#ef4444"),
        border_radius=8,
        padding=10,
        content=ft.Row(
            [
                ft.Icon(ft.icons.PRINT, size=16, color="#10b981" if sumatra_ok else "#ef4444"),
                ft.Text(
                    "Автопечать SumatraPDF готова" if sumatra_ok else "SumatraPDF.exe не найден",
                    size=11,
                    weight=ft.FontWeight.BOLD,
                    color="#10b981" if sumatra_ok else "#ef4444",
                ),
            ]
        ),
    )

    brand_title = ft.Text("СДЭК", weight=ft.FontWeight.BOLD, size=16, color=th()["text_primary"])
    brand_sub = ft.Text("Выписка накладных", size=11, weight=_w_sub(th()), color=th()["text_secondary"])
    nav_order_title = ft.Text("Электроконнект", size=13, weight=ft.FontWeight.BOLD, color=th()["text_primary"])
    nav_order_sub = ft.Text("Оформление СДЭК", size=11, weight=_w_sub(th()), color=th()["text_secondary"])
    nav_tracks_title = ft.Text("Треки", size=13, weight=ft.FontWeight.BOLD, color=th()["text_primary"])
    nav_tracks_sub = ft.Text("Копировать за день", size=11, weight=_w_sub(th()), color=th()["text_secondary"])
    nav_hist_title = ft.Text("История", size=13, weight=ft.FontWeight.BOLD, color=th()["text_primary"])
    nav_hist_sub = ft.Text("Архив накладных", size=11, weight=_w_sub(th()), color=th()["text_secondary"])
    themed_primary_texts.extend([brand_title, nav_order_title, nav_tracks_title, nav_hist_title])
    themed_secondary_texts.extend([brand_sub, nav_order_sub, nav_tracks_sub, nav_hist_sub])

    left_divider = ft.Divider(color=th()["border"])
    themed_dividers.append(left_divider)

    left_sidebar = ft.Container(
        width=215,
        bgcolor=th()["sidebar_bg"],
        padding=12,
        border=ft.border.only(right=ft.BorderSide(1, th()["border"])),
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.icons.LOCAL_SHIPPING, color="#10b981", size=26),
                        ft.Column([brand_title, brand_sub], spacing=0),
                    ]
                ),
                left_divider,
                ft.ListTile(
                    leading=ft.Icon(ft.icons.EDIT_DOCUMENT, color="#10b981"),
                    title=nav_order_title,
                    subtitle=nav_order_sub,
                    on_click=show_order,
                ),
                ft.ListTile(
                    leading=ft.Icon(ft.icons.RECEIPT_LONG, color="#10b981"),
                    title=nav_tracks_title,
                    subtitle=nav_tracks_sub,
                    on_click=show_tracks,
                ),
                ft.ListTile(
                    leading=ft.Icon(ft.icons.HISTORY, color="#94a3b8"),
                    title=nav_hist_title,
                    subtitle=nav_hist_sub,
                    on_click=show_history,
                ),
                ft.Container(expand=True),
                dd_theme,
                sumatra_badge,
            ],
            spacing=10,
        ),
    )

    right_sidebar = ft.Container(
        width=340,
        bgcolor=th()["sidebar_bg"],
        padding=14,
        border=ft.border.only(left=ft.BorderSide(1, th()["border"])),
        content=ft.Column([recipients_header, tf_search, recipients_list], spacing=10),
    )

    page.add(ft.Row([left_sidebar, center_container, right_sidebar], expand=True, spacing=0))
    refresh_recipients()
    refresh_tracks()
    refresh_history()


if __name__ == "__main__":
    ft.app(target=main)
