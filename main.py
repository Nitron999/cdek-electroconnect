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
            "Экспресс дверь-дверь",
            "Экспресс склад-склад",
            "Экспресс склад-дверь",
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
    tf_declared = styled_tf("Объявленная стоимость, ₽", "3000", accent=C_GOODS, width=210)

    # --- 4. ИНФОРМАЦИЯ ОБ ОТПРАВЛЕНИИ ---
    tf_pickup_address = styled_tf("Адрес забора курьером", "Сущёвская, 21, офис 426", accent=C_SHIP, expand=2)
    tf_courier_comment = styled_tf("Комментарий для курьера", "", accent=C_SHIP, expand=1)
    tf_pickup_date = styled_tf("Дата забора", tomorrow.strftime("%d.%m.%Y"), accent=C_SHIP, width=155)
    tf_time_from = styled_tf("Забор с", "12:00", accent=C_SHIP, width=105)
    tf_time_to = styled_tf("Забор до", "15:00", accent=C_SHIP, width=105)

    cb_attorney = ft.Checkbox(
        label="Курьеру необходима доверенность",
        value=False,
        active_color=C_SHIP,
        label_style=ft.TextStyle(color="#e2e8f0", size=13),
    )
    cb_id_doc = ft.Checkbox(
        label="Курьеру необходим документ удостоверяющий личность",
        value=False,
        active_color=C_SHIP,
        label_style=ft.TextStyle(color="#e2e8f0", size=13),
    )

    # Выбор ПВЗ / постамата / адреса доставки
    tf_pvz_code = styled_tf("Код ПВЗ", "IZHV16", accent=C_SHIP, width=130)
    tf_pvz_address = styled_tf("Адрес ПВЗ / постамата (или адрес доставки)", "ул. Азина, 135", accent=C_SHIP, expand=True)
    tf_pvz_search = styled_tf(
        label="Фильтр списка ПВЗ",
        hint_text="Введи улицу или код ПВЗ...",
        prefix_icon=ft.icons.SEARCH,
        accent=C_SHIP,
        expand=True,
    )
    dd_pvz_type_filter = styled_dd("Тип пункта", "Все", ["Все", "Пункт выдачи", "Постамат"], accent=C_SHIP, width=165)
    pvz_status_text = ft.Text(
        "Нажми «Загрузить ПВЗ», чтобы подтянуть пункты выдачи из интернета.",
        size=12,
        color="#94a3b8",
    )
    pvz_list_view = ft.ListView(height=150, spacing=5)

    # --- 5. КОММЕНТАРИЙ К ЗАКАЗУ ---
    tf_order_comment = styled_tf(
        "Комментарий к заказу",
        "УПД",
        accent=C_COMMENT,
        multiline=True,
        min_lines=2,
        max_lines=3,
    )

    cb_auto_save = ft.Checkbox(
        label="Если получателя нет в базе — автоматически сохранять его в справочник при создании заказа",
        value=True,
        active_color=C_RECIP,
        label_style=ft.TextStyle(color="#cbd5e1", size=12),
    )

    log_view = ft.ListView(height=72, spacing=2, auto_scroll=True)

    def add_log(msg: str):
        log_view.controls.append(ft.Text(msg, size=12, color="#cbd5e1"))
        page.update()

    # Быстрые кнопки дат и времени
    def set_date(d: datetime.date):
        tf_pickup_date.value = d.strftime("%d.%m.%Y")
        page.update()

    def set_interval(t1: str, t2: str):
        tf_time_from.value = t1
        tf_time_to.value = t2
        page.update()

    # --- ЛОГИКА ЗАГРУЗКИ И ВЫБОРА ПВЗ ---
    def select_pvz(item: dict):
        tf_pvz_code.value = item.get("code", "")
        tf_pvz_address.value = item.get("address", "")
        if item.get("type") == "Постамат":
            dd_delivery_to.value = "В ПОСТАМАТ"
        else:
            dd_delivery_to.value = "В ПВЗ"
        add_log(f"Выбран пункт: {item.get('code')} — {item.get('address')}")
        page.update()

    def render_pvz_list(_=None):
        query = (tf_pvz_search.value or "").strip().lower()
        t_filter = dd_pvz_type_filter.value
        pvz_list_view.controls.clear()

        for item in loaded_pvz:
            if t_filter != "Все" and item.get("type") != t_filter:
                continue
            haystack = f"{item.get('code', '')} {item.get('address', '')}".lower()
            if query and query not in haystack:
                continue

            is_postamat = item.get("type") == "Постамат"
            badge_color = "#38bdf8" if is_postamat else "#34d399"

            pvz_list_view.controls.append(
                ft.Container(
                    bgcolor="#161f30",
                    border=ft.border.all(1, "#26334a"),
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=10, vertical=7),
                    on_click=lambda e, it=item: select_pvz(it),
                    content=ft.Row(
                        [
                            ft.Container(width=9, height=9, border_radius=5, bgcolor=badge_color),
                            ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Text(item.get("code", ""), size=12, weight=ft.FontWeight.BOLD, color="#ffffff"),
                                            ft.Text(f"• {item.get('type', '')}", size=11, color=badge_color),
                                        ],
                                        spacing=6,
                                    ),
                                    ft.Text(item.get("address", ""), size=12, color="#e2e8f0"),
                                    ft.Text(item.get("work_time", ""), size=10, color="#94a3b8"),
                                ],
                                spacing=1,
                                expand=True,
                            ),
                            ft.Icon(ft.icons.CHECK_CIRCLE_OUTLINE, size=18, color=badge_color),
                        ]
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

    def on_load_pvz_click(_):
        btn_load_pvz.disabled = True
        pvz_status_text.value = f"Загружаю пункты выдачи для «{tf_city_to.value}»..."
        page.update()

        def worker():
            nonlocal loaded_pvz
            items, msg = fetch_cdek_pvz(tf_city_to.value)
            loaded_pvz = items
            pvz_status_text.value = msg
            btn_load_pvz.disabled = False
            render_pvz_list()

        threading.Thread(target=worker, daemon=True).start()

    btn_load_pvz.on_click = on_load_pvz_click
    tf_pvz_search.on_change = render_pvz_list
    dd_pvz_type_filter.on_change = render_pvz_list

    # --- СПРАВОЧНИК ПОЛУЧАТЕЛЕЙ (ПРАВАЯ ПАНЕЛЬ) ---
    tf_search = styled_tf(
        label="Поиск в базе",
        hint_text="Имя или город...",
        prefix_icon=ft.icons.SEARCH,
        accent=C_RECIP,
    )
    recipients_list = ft.ListView(expand=True, spacing=6)

    def apply_recipient(item: dict):
        dd_rec_type.value = item.get("recipient_type", "ФИЗ. ЛИЦО")
        tf_rec_fio.value = item.get("name", "")
        tf_rec_phone.value = item.get("phone", "")
        tf_rec_email.value = item.get("email", "")
        tf_city_to.value = item.get("city_to", "")
        tf_pvz_code.value = item.get("pvz_code", "")
        tf_pvz_address.value = item.get("pvz_address", "")
        dd_delivery_to.value = item.get("delivery_to", "В ПВЗ")
        tariff = item.get("tariff", "Экспресс дверь-склад")
        if any(opt.key == tariff for opt in dd_tariff.options):
            dd_tariff.value = tariff
        else:
            dd_tariff.value = "Экспресс дверь-склад"
        add_log(f"Загружен получатель: {item.get('name')}")
        page.update()

    def delete_recipient(item: dict):
        nonlocal recipients
        recipients = [r for r in recipients if r.get("name") != item.get("name")]
        save_recipients(recipients)
        refresh_recipients()

    def refresh_recipients(_=None):
        query = (tf_search.value or "").strip().lower()
        recipients_list.controls.clear()
        for item in recipients:
            if query and query not in item.get("name", "").lower() and query not in item.get("city_to", "").lower():
                continue
            recipients_list.controls.append(
                ft.Container(
                    bgcolor="#161f30",
                    border=ft.border.all(1, "#26334a"),
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=10, vertical=8),
                    content=ft.Row(
                        [
                            ft.Icon(ft.icons.PERSON, size=18, color=C_RECIP),
                            ft.Column(
                                [
                                    ft.Text(item.get("name", ""), size=13, weight=ft.FontWeight.W_600, color="#ffffff"),
                                    ft.Text(item.get("city_to", ""), size=11, color="#94a3b8"),
                                ],
                                spacing=1,
                                expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.icons.CLOSE,
                                icon_size=16,
                                icon_color="#94a3b8",
                                on_click=lambda e, it=item: delete_recipient(it),
                            ),
                        ],
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
            "delivery_to": dd_delivery_to.value,
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
        tf_rec_fio.value = ""
        tf_rec_phone.value = ""
        tf_rec_email.value = ""
        tf_city_to.value = ""
        tf_pvz_code.value = ""
        tf_pvz_address.value = ""
        add_log("Поля получателя очищены — можно вводить нового клиента.")
        page.update()

    tf_search.on_change = refresh_recipients
    recipients_header = ft.Text(
        f"Справочник получателей ({len(recipients)})",
        size=15,
        weight=ft.FontWeight.BOLD,
        color=C_RECIP,
    )

    # --- ЗАКРЕПЛЁННАЯ КНОПКА «СОЗДАТЬ ЗАКАЗ» ---
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

    def on_run_click(_):
        # Автоматически сохраняем нового получателя в базу, если включена галочка
        rec_name = tf_rec_fio.value.strip()
        if cb_auto_save.value and rec_name:
            exists = any(r.get("name", "").strip().lower() == rec_name.lower() for r in recipients)
            if not exists:
                save_current_to_base(silent=True)

        btn_run.disabled = True
        btn_run.text = "ОФОРМЛЯЮ НОВЫЙ ЗАКАЗ И ПЕЧАТАЮ..."
        log_view.controls.clear()
        page.update()

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
            "pickup_from": dd_pickup_from.value,
            "delivery_to": dd_delivery_to.value,
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

        def worker():
            try:
                run_cdek_order(order_payload, add_log)
            except Exception as exc:
                add_log(f"[ОШИБКА]: {exc}")
            finally:
                btn_run.disabled = False
                btn_run.text = "СОЗДАТЬ ЗАКАЗ И РАСПЕЧАТАТЬ НАКЛАДНУЮ"
                refresh_history()
                page.update()

        threading.Thread(target=worker, daemon=True).start()

    btn_run.on_click = on_run_click

    # --- КАРТОЧКА СЕКЦИИ С ЯРКОЙ ЦВЕТОВОЙ ПОЛОСОЙ И ИКОНКОЙ ---
    def section_card(title: str, icon, accent: str, controls: list):
        return ft.Container(
            bgcolor="#151d2e",
            border_radius=12,
            border=ft.border.only(
                left=ft.BorderSide(4, accent),
                top=ft.BorderSide(1, "#26334a"),
                right=ft.BorderSide(1, "#26334a"),
                bottom=ft.BorderSide(1, "#26334a"),
            ),
            padding=14,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(icon, color=accent, size=20),
                            ft.Text(title, size=15, weight=ft.FontWeight.BOLD, color=accent),
                        ],
                        spacing=8,
                    ),
                    *controls,
                ],
                spacing=10,
            ),
        )

    def sub_card(title: str, icon, accent: str, controls: list):
        return ft.Container(
            bgcolor="#101725",
            border_radius=10,
            border=ft.border.all(1, accent),
            padding=12,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(icon, color=accent, size=17),
                            ft.Text(title, size=13, weight=ft.FontWeight.BOLD, color=accent),
                        ],
                        spacing=6,
                    ),
                    *controls,
                ],
                spacing=10,
            ),
        )

    # --- ВКЛАДКА 1: ОФОРМЛЕНИЕ ---
    scrollable_form = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        spacing=14,
        controls=[
            ft.Container(
                bgcolor="#151d2e",
                border_radius=12,
                padding=14,
                border=ft.border.all(1, "#26334a"),
                content=ft.Row(
                    [
                        ft.Icon(ft.icons.LOCAL_SHIPPING, color="#10b981", size=30),
                        ft.Column(
                            [
                                ft.Text('ООО «ЭЛЕКТРОКОННЕКТ» — СДЭК', size=18, weight=ft.FontWeight.BOLD, color="#ffffff"),
                                ft.Text("ИНН 5408154542 • Всегда новый заказ • Автопечать SumatraPDF", size=12, color="#94a3b8"),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.OutlinedButton(
                            "Новый клиент",
                            icon=ft.icons.CLEAR_ALL,
                            on_click=clear_recipient_fields,
                        ),
                        ft.ElevatedButton(
                            "+ В базу",
                            icon=ft.icons.PERSON_ADD,
                            bgcolor="#2a2210",
                            color=C_RECIP,
                            style=ft.ButtonStyle(
                                side=ft.BorderSide(1, C_RECIP),
                                shape=ft.RoundedRectangleBorder(radius=8),
                            ),
                            on_click=save_current_to_base,
                        ),
                    ],
                    spacing=8,
                ),
            ),
            section_card(
                "1. О ЗАКАЗЕ И ДОСТУП",
                ft.icons.ASSIGNMENT,
                C_ORDER,
                [
                    sub_card("Доступ в личный кабинет lk.cdek.ru", ft.icons.LOCK_OPEN, C_ORDER, [ft.Row([tf_login, tf_password])]),
                    ft.Row([dd_role, dd_payer, tf_cost_center]),
                    ft.Row([tf_city_from, tf_city_to]),
                ],
            ),
            section_card(
                "2. ОТПРАВИТЕЛЬ И ПОЛУЧАТЕЛЬ",
                ft.icons.PEOPLE,
                C_RECIP,
                [
                    sub_card("ОТПРАВИТЕЛЬ", ft.icons.OUTBOX, C_SENDER, [ft.Row([tf_sender_company, tf_sender_fio, tf_sender_phone])]),
                    sub_card(
                        "ПОЛУЧАТЕЛЬ",
                        ft.icons.MOVE_TO_INBOX,
                        C_RECIP,
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
                C_GOODS,
                [
                    ft.Row([tf_weight, tf_length, tf_width, tf_height, tf_desc]),
                    ft.Row([dd_pickup_from, dd_delivery_to, dd_tariff]),
                    ft.Row([cb_insurance, tf_declared]),
                ],
            ),
            section_card(
                "4. ИНФОРМАЦИЯ ОБ ОТПРАВЛЕНИИ (ЗАБОР И ПВЗ / ПОСТАМАТ)",
                ft.icons.LOCATION_ON,
                C_SHIP,
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
                    ft.Divider(height=1, color="#26334a"),
                    ft.Text("Доставить в ПВЗ или постамат", size=13, weight=ft.FontWeight.BOLD, color=C_SHIP),
                    ft.Row([tf_pvz_code, tf_pvz_address, btn_load_pvz]),
                    ft.Row([tf_pvz_search, dd_pvz_type_filter]),
                    pvz_status_text,
                    ft.Container(
                        bgcolor="#0b101b",
                        border_radius=8,
                        padding=6,
                        border=ft.border.all(1, "#26334a"),
                        content=pvz_list_view,
                    ),
                ],
            ),
            section_card(
                "5. КОММЕНТАРИЙ К ЗАКАЗУ",
                ft.icons.COMMENT,
                C_COMMENT,
                [tf_order_comment, cb_auto_save],
            ),
        ],
    )

    pinned_footer = ft.Container(
        bgcolor="#131a29",
        border_radius=12,
        padding=12,
        border=ft.border.all(1, "#10b981"),
        content=ft.Column(
            [
                ft.Row([btn_run]),
                ft.Container(
                    bgcolor="#080c14",
                    border_radius=8,
                    padding=6,
                    content=log_view,
                ),
            ],
            spacing=8,
        ),
    )

    order_tab = ft.Column(
        expand=True,
        spacing=10,
        controls=[scrollable_form, pinned_footer],
    )

    # --- ВКЛАДКА 2: ИСТОРИЯ ---
    history_list = ft.ListView(expand=True, spacing=8)

    def refresh_history():
        history_list.controls.clear()
        for h in load_history():
            history_list.controls.append(
                ft.Container(
                    bgcolor="#151d2e",
                    border=ft.border.all(1, "#26334a"),
                    border_radius=10,
                    padding=12,
                    content=ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text(h.get("recipient", ""), weight=ft.FontWeight.BOLD, color="#ffffff"),
                                    ft.Text(
                                        f"{h.get('city_to', '')} • ПВЗ: {h.get('pvz', '')} • Забор: {h.get('date', '')}",
                                        size=12,
                                        color="#94a3b8",
                                    ),
                                ],
                                expand=True,
                            ),
                            ft.Text(h.get("created_at", ""), size=12, color="#64748b"),
                            ft.Icon(
                                ft.icons.PRINT if h.get("printed") else ft.icons.WARNING,
                                color="#10b981" if h.get("printed") else "#f59e0b",
                            ),
                        ]
                    ),
                )
            )

    history_tab = ft.Column(
        expand=True,
        controls=[
            ft.Text("История оформленных накладных", size=18, weight=ft.FontWeight.BOLD, color="#ffffff"),
            history_list,
        ],
    )

    center_container = ft.Container(expand=True, padding=14, content=order_tab)

    def show_order(_):
        center_container.content = order_tab
        page.update()

    def show_history(_):
        refresh_history()
        center_container.content = history_tab
        page.update()

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

    left_sidebar = ft.Container(
        width=230,
        bgcolor="#111827",
        padding=14,
        border=ft.border.only(right=ft.BorderSide(1, "#26334a")),
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.icons.LOCAL_SHIPPING, color="#10b981", size=26),
                        ft.Column(
                            [
                                ft.Text("СДЭК", weight=ft.FontWeight.BOLD, size=16, color="#ffffff"),
                                ft.Text("Выписка накладных", size=11, color="#94a3b8"),
                            ],
                            spacing=0,
                        ),
                    ]
                ),
                ft.Divider(color="#26334a"),
                ft.ListTile(
                    leading=ft.Icon(ft.icons.EDIT_DOCUMENT, color="#10b981"),
                    title=ft.Text("Электроконнект", size=13, weight=ft.FontWeight.W_600, color="#ffffff"),
                    subtitle=ft.Text("Оформление СДЭК", size=11, color="#94a3b8"),
                    on_click=show_order,
                ),
                ft.ListTile(
                    leading=ft.Icon(ft.icons.HISTORY, color="#94a3b8"),
                    title=ft.Text("История", size=13, weight=ft.FontWeight.W_600, color="#e2e8f0"),
                    subtitle=ft.Text("Архив накладных", size=11, color="#94a3b8"),
                    on_click=show_history,
                ),
                ft.Container(expand=True),
                sumatra_badge,
            ]
        ),
    )

    right_sidebar = ft.Container(
        width=310,
        bgcolor="#111827",
        padding=14,
        border=ft.border.only(left=ft.BorderSide(1, "#26334a")),
        content=ft.Column(
            [
                recipients_header,
                tf_search,
                recipients_list,
            ],
            spacing=10,
        ),
    )

    page.add(
        ft.Row(
            [left_sidebar, center_container, right_sidebar],
            expand=True,
            spacing=0,
        )
    )
    refresh_recipients()
    refresh_history()


if __name__ == "__main__":
    ft.app(target=main)
