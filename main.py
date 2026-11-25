import datetime
import queue
import re
import threading
import flet as ft
from storage import load_recipients, save_recipients, load_history
from printer import is_sumatra_ready
from cdek_pvz import fetch_cdek_pvz
from cdek_worker import run_cdek_order


THEMES = {
    "Тёмная ночь": {
        "mode": ft.ThemeMode.DARK,
        "page_bg": "#0b0f19",
        "sidebar_bg": "#111827",
        "card_bg": "#151d2e",
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
            "recip": "#fbbf24",
            "goods": "#c084fc",
            "ship": "#34d399",
            "comment": "#fb7185",
        },
    },
    "Светлая классика": {
        "mode": ft.ThemeMode.LIGHT,
        "page_bg": "#f1f5f9",
        "sidebar_bg": "#ffffff",
        "card_bg": "#ffffff",
        "subcard_bg": "#f8fafc",
        "input_bg": "#ffffff",
        "item_bg": "#f8fafc",
        "item_selected_bg": "#dcfce7",
        "footer_bg": "#ffffff",
        "log_bg": "#f1f5f9",
        "border": "#cbd5e1",
        "input_border": "#94a3b8",
        "text_primary": "#0f172a",
        "text_secondary": "#475569",
        "text_checkbox": "#1e293b",
        "pvz_addr": "#b45309",
        "accents": {
            "order": "#0284c7",
            "sender": "#2563eb",
            "recip": "#d97706",
            "goods": "#7c3aed",
            "ship": "#059669",
            "comment": "#e11d48",
        },
    },
    "Изумруд СДЭК": {
        "mode": ft.ThemeMode.DARK,
        "page_bg": "#061410",
        "sidebar_bg": "#0a1f19",
        "card_bg": "#0e2921",
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
            "sender": "#2dd4bf",
            "recip": "#facc15",
            "goods": "#a78bfa",
            "ship": "#4ade80",
            "comment": "#fb7185",
        },
    },
    "Глубокий океан": {
        "mode": ft.ThemeMode.DARK,
        "page_bg": "#071120",
        "sidebar_bg": "#0b192e",
        "card_bg": "#0f223d",
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
            "recip": "#fbbf24",
            "goods": "#c084fc",
            "ship": "#2dd4bf",
            "comment": "#f472b6",
        },
    },
    "Графит и золото": {
        "mode": ft.ThemeMode.DARK,
        "page_bg": "#121212",
        "sidebar_bg": "#1a1a1a",
        "card_bg": "#202020",
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
            "sender": "#f59e0b",
            "recip": "#fbbf24",
            "goods": "#d97706",
            "ship": "#22c55e",
            "comment": "#f87171",
        },
    },
    "Тёплый песок": {
        "mode": ft.ThemeMode.LIGHT,
        "page_bg": "#f5f0e6",
        "sidebar_bg": "#fbf8f1",
        "card_bg": "#fffdf9",
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
            "recip": "#b45309",
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


def main(page: ft.Page):
    page.title = "Электроконнект — СДЭК (Выписка накладных)"
    page.padding = 0
    page.window.width = 1380
    page.window.height = 880
    page.window.min_width = 1120
    page.window.min_height = 700

    current_theme_name = "Тёмная ночь"

    def th():
        return THEMES[current_theme_name]

    page.theme_mode = th()["mode"]
    page.bgcolor = th()["page_bg"]

    recipients = load_recipients()
    loaded_pvz: list[dict] = []
    pvz_load_seq = 0
    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)

    order_queue: queue.Queue = queue.Queue()
    queue_state = {"active": None, "pending": 0}
    queue_lock = threading.Lock()

    themed_inputs: list[tuple[ft.Control, str]] = []
    themed_checkboxes: list[tuple[ft.Checkbox, str]] = []
    themed_section_cards: list[tuple[ft.Container, ft.Icon, ft.Text, str]] = []
    themed_sub_cards: list[tuple[ft.Container, ft.Icon, ft.Text, str]] = []
    themed_primary_texts: list[ft.Text] = []
    themed_secondary_texts: list[ft.Text] = []
    themed_accent_texts: list[tuple[ft.Text, str]] = []
    themed_dividers: list[ft.Divider] = []

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
            dense=True,
            expand=expand,
            width=width,
            filled=True,
            fill_color=t["input_bg"],
            border_color=t["input_border"],
            focused_border_color=accent,
            border_radius=8,
            label_style=ft.TextStyle(color=accent, weight=ft.FontWeight.W_600, size=12),
            text_style=ft.TextStyle(color=t["text_primary"], weight=ft.FontWeight.W_500, size=14),
            hint_style=ft.TextStyle(color=t["text_secondary"], size=13),
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
            dense=True,
            expand=expand,
            width=width,
            filled=True,
            fill_color=t["input_bg"],
            border_color=t["input_border"],
            focused_border_color=accent,
            border_radius=8,
            label_style=ft.TextStyle(color=accent, weight=ft.FontWeight.W_600, size=12),
            text_style=ft.TextStyle(color=t["text_primary"], weight=ft.FontWeight.W_500, size=14),
        )
        themed_inputs.append((ctrl, accent_key))
        return ctrl

    def styled_cb(label: str, value: bool, accent_key: str, size: int = 13) -> ft.Checkbox:
        t = th()
        cb = ft.Checkbox(
            label=label,
            value=value,
            active_color=t["accents"][accent_key],
            label_style=ft.TextStyle(color=t["text_checkbox"], size=size),
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
    tf_city_to = styled_tf("Город получателя", "Ижевск, Удмуртия, Россия", accent_key="order", expand=1)

    # --- 2. ОТПРАВИТЕЛЬ И ПОЛУЧАТЕЛЬ ---
    tf_sender_company = styled_tf("Компания (ИНН 5408154542)", '"ЭЛЕКТРОКОННЕКТ"', accent_key="sender", expand=1)
    tf_sender_fio = styled_tf("ФИО отправителя", "Крылова Людмила Борисовна", accent_key="sender", expand=1)
    tf_sender_phone = styled_tf("Телефон отправителя", "+7 916 195 36 94", accent_key="sender", expand=1)

    dd_rec_type = styled_dd("Тип получателя", "ФИЗ. ЛИЦО", ["ФИЗ. ЛИЦО", "ЮР. ЛИЦО"], accent_key="recip", expand=1)
    tf_rec_fio = styled_tf("ФИО / Название получателя", "Патрушев Илья Сергеевич", accent_key="recip", expand=2)
    tf_rec_phone = styled_tf("Телефон получателя", "+7 950 152 10 79", accent_key="recip", expand=1)
    tf_rec_email = styled_tf("Электронная почта", "", accent_key="recip", expand=1)

    # --- 3. ТОВАРЫ, ТАРИФ И ДОП. УСЛУГИ ---
    tf_weight = styled_tf("Вес, кг", "0.5", accent_key="goods", expand=1)
    tf_length = styled_tf("Длина, см", "10", accent_key="goods", expand=1)
    tf_width = styled_tf("Ширина, см", "10", accent_key="goods", expand=1)
    tf_height = styled_tf("Высота, см", "5", accent_key="goods", expand=1)
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
    tf_declared = styled_tf("Объявленная стоимость, ₽", "3000", accent_key="goods", width=210)

    # --- 4. ИНФОРМАЦИЯ ОБ ОТПРАВЛЕНИИ ---
    tf_pickup_address = styled_tf("Адрес забора курьером", "Сущёвская, 21, офис 426", accent_key="ship", expand=2)
    tf_courier_comment = styled_tf("Комментарий для курьера", "", accent_key="ship", expand=1)
    tf_pickup_date = styled_tf("Дата забора", tomorrow.strftime("%d.%m.%Y"), accent_key="ship", width=155)
    tf_time_from = styled_tf("Забор с", "12:00", accent_key="ship", width=105)
    tf_time_to = styled_tf("Забор до", "15:00", accent_key="ship", width=105)

    cb_attorney = styled_cb("Курьеру необходима доверенность", False, "ship")
    cb_id_doc = styled_cb("Курьеру необходим документ удостоверяющий личность", False, "ship")

    tf_pvz_code = styled_tf("Код ПВЗ", "IZHV16", accent_key="ship", width=130)
    tf_pvz_address = styled_tf("Адрес ПВЗ (или адрес доставки)", "ул. Азина, 135", accent_key="ship", expand=True)

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
    dd_pvz_type_filter = styled_dd("Тип пункта", "Пункт выдачи", ["Все", "Пункт выдачи", "Постамат"], accent_key="ship", width=165)
    pvz_status_text = ft.Text(
        "При выборе клиента из базы ПВЗ города подгружаются автоматически.",
        size=12,
        color=th()["text_secondary"],
    )
    themed_secondary_texts.append(pvz_status_text)
    pvz_list_view = ft.ListView(height=270, spacing=6)

    # --- 5. КОММЕНТАРИЙ К ЗАКАЗУ ---
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
        log_view.controls.append(ft.Text(msg, size=12, color=th()["text_primary"]))
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
                    border_radius=9,
                    padding=ft.padding.symmetric(horizontal=12, vertical=9),
                    on_click=lambda e, it=item: select_pvz(it),
                    content=ft.Row(
                        [
                            ft.Container(width=10, height=10, border_radius=5, bgcolor=badge_color),
                            ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Container(
                                                bgcolor=t["input_bg"],
                                                border=ft.border.all(1, badge_color),
                                                border_radius=5,
                                                padding=ft.padding.symmetric(horizontal=7, vertical=2),
                                                content=ft.Text(
                                                    item.get("code", "") or "ПВЗ",
                                                    size=12,
                                                    weight=ft.FontWeight.BOLD,
                                                    color=badge_color,
                                                ),
                                            ),
                                            ft.Text(
                                                item.get("type", ""),
                                                size=12,
                                                weight=ft.FontWeight.W_600,
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
                                                color=t["text_secondary"],
                                            ),
                                        ],
                                        spacing=8,
                                        wrap=True,
                                    ),
                                    ft.Text(
                                        item.get("address", ""),
                                        size=15,
                                        weight=ft.FontWeight.BOLD,
                                        color=t["pvz_addr"],
                                    ),
                                ],
                                spacing=4,
                                expand=True,
                            ),
                            ft.Icon(
                                ft.icons.CHECK_CIRCLE if is_selected else ft.icons.CHECK_CIRCLE_OUTLINE,
                                size=20,
                                color=badge_color,
                            ),
                        ],
                        spacing=10,
                    ),
                )
            )

        if loaded_pvz and matched_count == 0:
            pvz_list_view.controls.append(
                ft.Container(
                    padding=12,
                    content=ft.Text(
                        "По фильтру ничего не найдено — нажми × в строке фильтра, чтобы показать все пункты города.",
                        size=13,
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
        hint_text="Имя или город...",
        prefix_icon=ft.icons.SEARCH,
        accent_key="recip",
    )
    recipients_list = ft.ListView(expand=True, spacing=6)

    def apply_recipient(item: dict):
        nonlocal loaded_pvz
        dd_rec_type.value = item.get("recipient_type", "ФИЗ. ЛИЦО")
        tf_rec_fio.value = item.get("name", "")
        tf_rec_phone.value = item.get("phone", "")
        tf_rec_email.value = item.get("email", "")
        tf_city_to.value = item.get("city_to", "")
        tf_pvz_code.value = item.get("pvz_code", "")
        tf_pvz_address.value = item.get("pvz_address", "")
        dd_delivery_to.value = "В ПВЗ"
        tariff = item.get("tariff", "Экспресс дверь-склад")
        if any(opt.key == tariff for opt in dd_tariff.options):
            dd_tariff.value = tariff
        else:
            dd_tariff.value = "Экспресс дверь-склад"

        if item.get("time_from"):
            tf_time_from.value = item["time_from"]
        if item.get("time_to"):
            tf_time_to.value = item["time_to"]

        tf_pvz_search.value = ""
        dd_pvz_type_filter.value = "Пункт выдачи"
        loaded_pvz = []
        pvz_list_view.controls.clear()
        add_log(f"Загружен получатель: {item.get('name')} — подтягиваю ПВЗ...")
        page.update()

        if item.get("city_to"):
            start_pvz_fetch(
                city=item.get("city_to", ""),
                target_code=item.get("pvz_code", ""),
                target_addr=item.get("pvz_address", ""),
                auto_select=True,
            )

    def open_edit_recipient_dialog(item: dict):
        orig_name = item.get("name", "")
        ed_type = ft.Dropdown(
            label="Тип получателя",
            value=item.get("recipient_type", "ФИЗ. ЛИЦО"),
            options=[ft.dropdown.Option("ФИЗ. ЛИЦО"), ft.dropdown.Option("ЮР. ЛИЦО")],
            dense=True,
        )
        ed_name = ft.TextField(label="ФИО / Название компании", value=orig_name, dense=True)
        ed_phone = ft.TextField(label="Телефон", value=item.get("phone", ""), dense=True)
        ed_email = ft.TextField(label="Электронная почта", value=item.get("email", ""), dense=True)
        ed_city = ft.TextField(label="Город получателя", value=item.get("city_to", ""), dense=True)
        ed_pvz_code = ft.TextField(label="Код ПВЗ", value=item.get("pvz_code", ""), dense=True, width=140)
        ed_pvz_addr = ft.TextField(label="Адрес ПВЗ", value=item.get("pvz_address", ""), dense=True, expand=True)
        ed_time_from = ft.TextField(label="Забор с", value=item.get("time_from", "12:00"), dense=True, width=120)
        ed_time_to = ft.TextField(label="Забор до", value=item.get("time_to", "15:00"), dense=True, width=120)
        cur_tariff = item.get("tariff", "Экспресс дверь-склад")
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
            new_name = (ed_name.value or "").strip()
            if not new_name:
                return
            updated = {
                "name": new_name,
                "template": new_name,
                "recipient_type": ed_type.value,
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

            if (tf_rec_fio.value or "").strip().lower() == orig_name.strip().lower():
                apply_recipient(updated)

            add_log(f"Обновлён получатель в базе: {new_name}")
            page.close(dlg)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Редактировать получателя", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=500,
                content=ft.Column(
                    [
                        ed_type,
                        ed_name,
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
            if query and query not in item.get("name", "").lower() and query not in item.get("city_to", "").lower():
                continue
            recipients_list.controls.append(
                ft.Container(
                    bgcolor=t["item_bg"],
                    border=ft.border.all(1, t["border"]),
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=10, vertical=8),
                    content=ft.Row(
                        [
                            ft.Icon(ft.icons.PERSON, size=18, color=t["accents"]["recip"]),
                            ft.Column(
                                [
                                    ft.Text(
                                        item.get("name", ""),
                                        size=13,
                                        weight=ft.FontWeight.W_600,
                                        color=t["text_primary"],
                                    ),
                                    ft.Text(item.get("city_to", ""), size=11, color=t["text_secondary"]),
                                ],
                                spacing=1,
                                expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.icons.EDIT,
                                icon_size=17,
                                icon_color=t["accents"]["order"],
                                tooltip="Редактировать / удалить получателя",
                                on_click=lambda e, it=item: open_edit_recipient_dialog(it),
                            ),
                        ],
                        spacing=4,
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    on_click=lambda e, it=item: apply_recipient(it),
                )
            )
        recipients_header.value = f"Справочник получателей ({len(recipients)})"
        page.update()

    def save_current_to_base(_=None, silent: bool = False):
        name = tf_rec_fio.value.strip()
        if not name:
            if not silent:
                add_log("Введи ФИО получателя, чтобы сохранить в базу.")
            return
        new_item = {
            "name": name,
            "template": name,
            "recipient_type": dd_rec_type.value,
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
        nonlocal recipients
        recipients = [r for r in recipients if r.get("name", "").strip().lower() != name.lower()]
        recipients.insert(0, new_item)
        save_recipients(recipients)
        refresh_recipients()
        if not silent:
            add_log(f"Сохранено в справочник: {name}")

    def clear_recipient_fields(_):
        nonlocal loaded_pvz
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
            rec_name = payload.get("recipient_fio") or "Заказ"
            with queue_lock:
                queue_state["pending"] = max(0, queue_state["pending"] - 1)
                queue_state["active"] = rec_name
            update_queue_badge()
            add_log(f"=== Старт заказа: {rec_name} ({payload.get('city_to', '')}) ===")
            try:
                run_cdek_order(payload, add_log)
            except Exception as exc:
                add_log(f"[ОШИБКА {rec_name}]: {exc}")
            finally:
                with queue_lock:
                    queue_state["active"] = None
                refresh_history()
                update_queue_badge()
                order_queue.task_done()

    threading.Thread(target=queue_worker_loop, daemon=True).start()

    def on_run_click(_):
        rec_name = tf_rec_fio.value.strip()
        if cb_auto_save.value and rec_name:
            exists = any(r.get("name", "").strip().lower() == rec_name.lower() for r in recipients)
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
            "recipient_type": dd_rec_type.value,
            "recipient_fio": tf_rec_fio.value,
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
        add_log(f"+ Добавлен в очередь (#{pos}): {rec_name or 'Без имени'} — {tf_city_to.value}")
        update_queue_badge()

    btn_run.on_click = on_run_click

    # --- КАРТОЧКИ СЕКЦИЙ ---
    def section_card(title: str, icon, accent_key: str, controls: list):
        t = th()
        accent = t["accents"][accent_key]
        ic = ft.Icon(icon, color=accent, size=20)
        tx = ft.Text(title, size=15, weight=ft.FontWeight.BOLD, color=accent)
        box = ft.Container(
            bgcolor=t["card_bg"],
            border_radius=12,
            border=ft.border.only(
                left=ft.BorderSide(4, accent),
                top=ft.BorderSide(1, t["border"]),
                right=ft.BorderSide(1, t["border"]),
                bottom=ft.BorderSide(1, t["border"]),
            ),
            padding=14,
            content=ft.Column([ft.Row([ic, tx], spacing=8), *controls], spacing=10),
        )
        themed_section_cards.append((box, ic, tx, accent_key))
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
        padding=8,
        border=ft.border.all(1, th()["border"]),
        content=pvz_list_view,
    )

    # --- ВКЛАДКА 1: ОФОРМЛЕНИЕ ---
    scrollable_form = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        spacing=14,
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
                "2. ОТПРАВИТЕЛЬ И ПОЛУЧАТЕЛЬ",
                ft.icons.PEOPLE,
                "recip",
                [
                    sub_card("ОТПРАВИТЕЛЬ", ft.icons.OUTBOX, "sender", [ft.Row([tf_sender_company, tf_sender_fio, tf_sender_phone])]),
                    sub_card(
                        "ПОЛУЧАТЕЛЬ",
                        ft.icons.MOVE_TO_INBOX,
                        "recip",
                        [
                            ft.Row([dd_rec_type, tf_rec_fio, tf_rec_phone]),
                            ft.Row([tf_rec_email]),
                        ],
                    ),
                ],
            ),
            section_card(
                "3. ТОВАРЫ, ТАРИФ И ДОП. УСЛУГИ",
                ft.icons.INVENTORY_2,
                "goods",
                [
                    ft.Row([tf_weight, tf_length, tf_width, tf_height, tf_desc]),
                    ft.Row([dd_pickup_from, dd_delivery_to, dd_tariff]),
                    ft.Row([cb_insurance, tf_declared]),
                ],
            ),
            section_card(
                "4. ИНФОРМАЦИЯ ОБ ОТПРАВЛЕНИИ (ЗАБОР И ПВЗ)",
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
                "5. КОММЕНТАРИЙ К ЗАКАЗУ",
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

    # --- ВКЛАДКА 2: ИСТОРИЯ ---
    history_list = ft.ListView(expand=True, spacing=8)
    history_title = ft.Text("История оформленных накладных", size=18, weight=ft.FontWeight.BOLD, color=th()["text_primary"])
    themed_primary_texts.append(history_title)

    def refresh_history():
        t = th()
        history_list.controls.clear()
        for h in load_history():
            history_list.controls.append(
                ft.Container(
                    bgcolor=t["card_bg"],
                    border=ft.border.all(1, t["border"]),
                    border_radius=10,
                    padding=12,
                    content=ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text(h.get("recipient", ""), weight=ft.FontWeight.BOLD, color=t["text_primary"]),
                                    ft.Text(
                                        f"{h.get('city_to', '')} • ПВЗ: {h.get('pvz', '')} • Забор: {h.get('date', '')}",
                                        size=12,
                                        color=t["text_secondary"],
                                    ),
                                ],
                                expand=True,
                            ),
                            ft.Text(h.get("created_at", ""), size=12, color=t["text_secondary"]),
                            ft.Icon(
                                ft.icons.PRINT if h.get("printed") else ft.icons.WARNING,
                                color="#10b981" if h.get("printed") else "#f59e0b",
                            ),
                        ]
                    ),
                )
            )

    history_tab = ft.Column(expand=True, controls=[history_title, history_list])
    center_container = ft.Container(expand=True, padding=14, content=order_tab)

    def show_order(_):
        center_container.content = order_tab
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
            ctrl.label_style = ft.TextStyle(color=acc, weight=ft.FontWeight.W_600, size=12)
            ctrl.text_style = ft.TextStyle(color=t["text_primary"], weight=ft.FontWeight.W_500, size=14)
            if hasattr(ctrl, "hint_style"):
                ctrl.hint_style = ft.TextStyle(color=t["text_secondary"], size=13)

        for cb, akey in themed_checkboxes:
            cb.active_color = t["accents"][akey]
            cb.label_style = ft.TextStyle(color=t["text_checkbox"], size=cb.label_style.size if cb.label_style else 13)

        for box, ic, tx, akey in themed_section_cards:
            acc = t["accents"][akey]
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
        for tx in themed_secondary_texts:
            tx.color = t["text_secondary"]
        for tx, akey in themed_accent_texts:
            tx.color = t["accents"][akey]
        for dv in themed_dividers:
            dv.color = t["border"]

        render_pvz_list()
        refresh_recipients()
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
                    weight=ft.FontWeight.W_600,
                    color="#10b981" if sumatra_ok else "#ef4444",
                ),
            ]
        ),
    )

    brand_title = ft.Text("СДЭК", weight=ft.FontWeight.BOLD, size=16, color=th()["text_primary"])
    brand_sub = ft.Text("Выписка накладных", size=11, color=th()["text_secondary"])
    nav_order_title = ft.Text("Электроконнект", size=13, weight=ft.FontWeight.W_600, color=th()["text_primary"])
    nav_order_sub = ft.Text("Оформление СДЭК", size=11, color=th()["text_secondary"])
    nav_hist_title = ft.Text("История", size=13, weight=ft.FontWeight.W_600, color=th()["text_primary"])
    nav_hist_sub = ft.Text("Архив накладных", size=11, color=th()["text_secondary"])
    themed_primary_texts.extend([brand_title, nav_order_title, nav_hist_title])
    themed_secondary_texts.extend([brand_sub, nav_order_sub, nav_hist_sub])

    left_divider = ft.Divider(color=th()["border"])
    themed_dividers.append(left_divider)

    left_sidebar = ft.Container(
        width=235,
        bgcolor=th()["sidebar_bg"],
        padding=14,
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
        width=325,
        bgcolor=th()["sidebar_bg"],
        padding=14,
        border=ft.border.only(left=ft.BorderSide(1, th()["border"])),
        content=ft.Column([recipients_header, tf_search, recipients_list], spacing=10),
    )

    page.add(ft.Row([left_sidebar, center_container, right_sidebar], expand=True, spacing=0))
    refresh_recipients()
    refresh_history()


if __name__ == "__main__":
    ft.app(target=main)
