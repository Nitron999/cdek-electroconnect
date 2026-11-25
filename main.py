import datetime
import threading
import flet as ft
from storage import load_recipients, save_recipients, load_history
from printer import is_sumatra_ready
from cdek_pvz import fetch_cdek_pvz
from cdek_worker import run_cdek_order


def main(page: ft.Page):
    page.title = "Электроконнект — СДЭК (Выписка накладных)"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0b0f19"
    page.padding = 0
    page.window.width = 1380
    page.window.height = 880
    page.window.min_width = 1120
    page.window.min_height = 700

    recipients = load_recipients()
    loaded_pvz: list[dict] = []
    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)

    # --- ХЕЛПЕРЫ ДЛЯ КОНТРАСТНЫХ ПОЛЕЙ ---
    def styled_tf(
        label: str,
        value: str = "",
        accent: str = "#38bdf8",
        expand=None,
        width=None,
        password: bool = False,
        can_reveal_password: bool = False,
        multiline: bool = False,
        min_lines: int = 1,
        max_lines: int = 1,
        hint_text: str | None = None,
        prefix_icon=None,
    ) -> ft.TextField:
        return ft.TextField(
            label=label,
            value=value,
            hint_text=hint_text,
            prefix_icon=prefix_icon,
            password=password,
            can_reveal_password=can_reveal_password,
            multiline=multiline,
            min_lines=min_lines,
            max_lines=max_lines,
            dense=True,
            expand=expand,
            width=width,
            filled=True,
            fill_color="#0b101b",
            border_color="#334155",
            focused_border_color=accent,
            border_radius=8,
            label_style=ft.TextStyle(color=accent, weight=ft.FontWeight.W_600, size=12),
            text_style=ft.TextStyle(color="#ffffff", weight=ft.FontWeight.W_500, size=14),
            hint_style=ft.TextStyle(color="#64748b", size=13),
        )

    def styled_dd(
        label: str,
        value: str,
        options: list[str],
        accent: str = "#38bdf8",
        expand=None,
        width=None,
    ) -> ft.Dropdown:
        return ft.Dropdown(
            label=label,
            value=value,
            options=[ft.dropdown.Option(x) for x in options],
            dense=True,
            expand=expand,
            width=width,
            filled=True,
            fill_color="#0b101b",
            border_color="#334155",
            focused_border_color=accent,
            border_radius=8,
            label_style=ft.TextStyle(color=accent, weight=ft.FontWeight.W_600, size=12),
            text_style=ft.TextStyle(color="#ffffff", weight=ft.FontWeight.W_500, size=14),
        )

    # Цветовые акценты по блокам
    C_ORDER = "#38bdf8"      # Голубой — О заказе и доступ
    C_SENDER = "#60a5fa"     # Синий — Отправитель
    C_RECIP = "#fbbf24"      # Золотой — Получатель
    C_GOODS = "#c084fc"      # Фиолетовый — Товары и тариф
    C_SHIP = "#34d399"       # Изумрудный — Забор и ПВЗ
    C_COMMENT = "#fb7185"    # Коралловый — Комментарий

    # --- 1. О ЗАКАЗЕ И ДОСТУП ---
    tf_login = styled_tf("Логин СДЭК", "Msk001", accent=C_ORDER, expand=1)
    tf_password = styled_tf(
        "Пароль СДЭК",
        "#Ljcneg2026",
        accent=C_ORDER,
        password=True,
        can_reveal_password=True,
        expand=1,
    )
    tf_template = styled_tf("Шаблон заказа", "Патрушев Илья Сергеевич", accent=C_ORDER, expand=2)
    dd_role = styled_dd(
        "Кем я являюсь",
        "ОТПРАВИТЕЛЕМ",
        ["ОТПРАВИТЕЛЕМ", "ПОЛУЧАТЕЛЕМ", "ТРЕТЬЕЙ СТОРОНОЙ"],
        accent=C_ORDER,
        expand=1,
    )
    dd_payer = styled_dd(
        "Оплата",
        "ПО ДОГОВОРУ",
        ["ПО ДОГОВОРУ", "ОТПРАВИТЕЛЕМ", "ПОЛУЧАТЕЛЕМ"],
        accent=C_ORDER,
        expand=1,
    )
    tf_cost_center = styled_tf("Центр затрат", "Москва", accent=C_ORDER, expand=1)
    tf_city_from = styled_tf("Город отправителя", "Москва, Москва, Россия", accent=C_ORDER, expand=1)
    tf_city_to = styled_tf("Город получателя", "Ижевск, Удмуртия, Россия", accent=C_ORDER, expand=1)

    # --- 2. ОТПРАВИТЕЛЬ И ПОЛУЧАТЕЛЬ ---
    tf_sender_company = styled_tf("Компания (ИНН 5408154542)", '"ЭЛЕКТРОКОННЕКТ"', accent=C_SENDER, expand=1)
    tf_sender_fio = styled_tf("ФИО отправителя", "Крылова Людмила Борисовна", accent=C_SENDER, expand=1)
    tf_sender_phone = styled_tf("Телефон отправителя", "+7 916 195 36 94", accent=C_SENDER, expand=1)

    dd_rec_type = styled_dd("Тип получателя", "ФИЗ. ЛИЦО", ["ФИЗ. ЛИЦО", "ЮР. ЛИЦО"], accent=C_RECIP, expand=1)
    tf_rec_fio = styled_tf("ФИО / Название получателя", "Патрушев Илья Сергеевич", accent=C_RECIP, expand=2)
    tf_rec_phone = styled_tf("Телефон получателя", "+7 950 152 10 79", accent=C_RECIP, expand=1)
    tf_rec_email = styled_tf("Электронная почта", "", accent=C_RECIP, expand=1)

    # --- 3. ТОВАРЫ, ТАРИФ И ДОП. УСЛУГИ ---
    tf_weight = styled_tf("Вес, кг", "0.5", accent=C_GOODS, expand=1)
    tf_length = styled_tf("Длина, см", "10", accent=C_GOODS, expand=1)
    tf_width = styled_tf("Ширина, см", "10", accent=C_GOODS, expand=1)
    tf_height = styled_tf("Высота, см", "5", accent=C_GOODS, expand=1)
    tf_desc = styled_tf("Описание груза", "ПЛАТЫ", accent=C_GOODS, expand=2)

    dd_pickup_from = styled_dd(
        "Откуда",
        "КУРЬЕР ЗАБЕРЁТ ПО АДРЕСУ",
        ["КУРЬЕР ЗАБЕРЁТ ПО АДРЕСУ", "ИЗ ПВЗ"],
        accent=C_GOODS,
        expand=1,
    )
    dd_delivery_to = styled_dd(
        "Куда доставить",
        "В ПВЗ",
        ["В ПВЗ", "В ПОСТАМАТ", "КУРЬЕРОМ ПО АДРЕСУ"],
        accent=C_GOODS,
        expand=1,
    )
    dd_tariff = styled_dd(
        "Тариф",
        "Экспресс дверь-склад",
        [
            "Посылка дверь-склад",
            "СДЭК Документы дверь-склад",
            "Экспресс дверь-склад",
            "Супер-экспресс до 18 дверь-склад",
            "Супер-экспресс до 16 дверь-склад",
            "Магистральный экспресс дверь-склад",
        ],
        accent=C_GOODS,
        expand=2,
    )
    cb_insurance = ft.Checkbox(
        label="Дополнительный сбор за объявленную стоимость",
        value=True,
        active_color=C_GOODS,
        label_style=ft.TextStyle(color="#e2e8f0", size=13),
    )
    tf_declared = styled_tf("Об
