import datetime
import threading
import flet as ft
from storage import load_recipients, save_recipients, load_history
from printer import is_sumatra_ready
from cdek_worker import run_cdek_order


def main(page: ft.Page):
    page.title = "Электроконнект — СДЭК (Выписка накладных)"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0f141e"
    page.padding = 0
    page.window.width = 1360
    page.window.height = 860
    page.window.min_width = 1100
    page.window.min_height = 700

    recipients = load_recipients()
    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)

    # --- ПОЛЯ ФОРМЫ (все параметры со скриншотов СДЭК) ---
    tf_login = ft.TextField(label="Логин СДЭК", value="KU-TOM11-8", dense=True, expand=1)
    tf_password = ft.TextField(
        label="Пароль СДЭК", value="Ddf343rg@3!ertb", password=True, can_reveal_password=True, dense=True, expand=1
    )

    # 1. О заказе
    tf_template = ft.TextField(label="Шаблон заказа (если есть в СДЭК)", value="Патрушев Илья Сергеевич", dense=True, expand=2)
    dd_role = ft.Dropdown(
        label="Кем я являюсь",
        value="ОТПРАВИТЕЛЕМ",
        options=[ft.dropdown.Option(x) for x in ["ОТПРАВИТЕЛЕМ", "ПОЛУЧАТЕЛЕМ", "ТРЕТЬЕЙ СТОРОНОЙ"]],
        dense=True,
        expand=1,
    )
    dd_payer = ft.Dropdown(
        label="Оплата",
        value="ПО ДОГОВОРУ",
        options=[ft.dropdown.Option(x) for x in ["ПО ДОГОВОРУ", "ОТПРАВИТЕЛЕМ", "ПОЛУЧАТЕЛЕМ"]],
        dense=True,
        expand=1,
    )
    tf_cost_center = ft.TextField(label="Центр затрат", value="Москва", dense=True, expand=1)
    tf_city_from = ft.TextField(label="Город отправителя", value="Москва, Москва, Россия", dense=True, expand=1)
    tf_city_to = ft.TextField(label="Город получателя", value="Ижевск, Удмуртия, Россия", dense=True, expand=1)

    # 2. Отправитель
    tf_sender_company = ft.TextField(label="Компания (ИНН 5408154542)", value='"ЭЛЕКТРОКОННЕКТ"', dense=True, expand=1)
    tf_sender_fio = ft.TextField(label="ФИО отправителя", value="Крылова Людмила Борисовна", dense=True, expand=1)
    tf_sender_phone = ft.TextField(label="Телефон отправителя", value="+7 916 195 36 94", dense=True, expand=1)

    # 3. Получатель
    dd_rec_type = ft.Dropdown(
        label="Тип получателя",
        value="ФИЗ. ЛИЦО",
        options=[ft.dropdown.Option("ФИЗ. ЛИЦО"), ft.dropdown.Option("ЮР. ЛИЦО")],
        dense=True,
        expand=1,
    )
    tf_rec_fio = ft.TextField(label="ФИО / Название получателя", value="Патрушев Илья Сергеевич", dense=True, expand=2)
    tf_rec_phone = ft.TextField(label="Телефон получателя", value="+7 950 152 10 79", dense=True, expand=1)
    tf_rec_email = ft.TextField(label="Электронная почта (необязательно)", value="", dense=True, expand=1)

    # 4. Товары
    tf_weight = ft.TextField(label="Вес, кг", value="0.5", dense=True, expand=1)
    tf_length = ft.TextField(label="Длина, см", value="10", dense=True, expand=1)
    tf_width = ft.TextField(label="Ширина, см", value="10", dense=True, expand=1)
    tf_height = ft.TextField(label="Высота, см", value="5", dense=True, expand=1)
    tf_desc = ft.TextField(label="Описание груза", value="ПЛАТЫ", dense=True, expand=2)

    # 5. Тарифы и доп. услуги
    dd_pickup_from = ft.Dropdown(
        label="Откуда",
        value="КУРЬЕР ЗАБЕРЁТ ПО АДРЕСУ",
        options=[ft.dropdown.Option("КУРЬЕР ЗАБЕРЁТ ПО АДРЕСУ"), ft.dropdown.Option("ИЗ ПВЗ")],
        dense=True,
        expand=1,
    )
    dd_delivery_to = ft.Dropdown(
        label="Куда доставить",
        value="В ПВЗ",
        options=[ft.dropdown.Option("В ПВЗ"), ft.dropdown.Option("В ПОСТАМАТ"), ft.dropdown.Option("КУРЬЕРОМ ПО АДРЕСУ")],
        dense=True,
        expand=1,
    )
    dd_tariff = ft.Dropdown(
        label="Тариф",
        value="Экспресс дверь-склад",
        options=[
            ft.dropdown.Option("Посылка дверь-склад"),
            ft.dropdown.Option("СДЭК Документы дверь-склад"),
            ft.dropdown.Option("Экспресс дверь-склад"),
            ft.dropdown.Option("Супер-экспресс до 18 дверь-склад"),
            ft.dropdown.Option("Супер-экспресс до 16 дверь-склад"),
            ft.dropdown.Option("Магистральный экспресс дверь-склад"),
        ],
        dense=True,
        expand=2,
    )
    cb_insurance = ft.Checkbox(label="Объявленная стоимость", value=True)
    tf_declared = ft.TextField(label="Сумма, ₽", value="3000", dense=True, width=140)

    # 6. Информация об отправлении
    tf_pickup_address = ft.TextField(label="Адрес забора курьером", value="Сущевская 21 оф 426", dense=True, expand=2)
    tf_courier_comment = ft.TextField(label="Комментарий для курьера", value="", dense=True, expand=1)
    tf_pickup_date = ft.TextField(label="Дата забора", value=tomorrow.strftime("%d.%m.%Y"), dense=True, expand=1)
    tf_time_from = ft.TextField(label="Время с", value="12:00", dense=True, width=100)
    tf_time_to = ft.TextField(label="Время до", value="15:00", dense=True, width=100)
    tf_pvz = ft.TextField(label="ПВЗ / Адрес получателя", value="ул. Азина, 135", dense=True, expand=1)
    tf_order_comment = ft.TextField(label="Комментарий к заказу", value="УПД", dense=True, expand=1)

    cb_auto_submit = ft.Checkbox(
        label="Автоматически нажать «СОЗДАТЬ ЗАКАЗ» (если снять — сможешь проверить ПВЗ глазами)",
        value=True,
    )

    log_view = ft.ListView(height=110, spacing=3, auto_scroll=True)

    def add_log(msg: str):
        log_view.controls.append(ft.Text(msg, size=12, color="#94a3b8"))
        page.update()

    # Быстрые кнопки дат и времени
    def set_date(d: datetime.date):
        tf_pickup_date.value = d.strftime("%d.%m.%Y")
        page.update()

    def set_interval(t1: str, t2: str):
        tf_time_from.value = t1
        tf_time_to.value = t2
        page.update()

    # --- СПРАВОЧНИК ПОЛУЧАТЕЛЕЙ (ПРАВАЯ ПАНЕЛЬ) ---
    tf_search = ft.TextField(
        hint_text="Поиск получателя...",
        prefix_icon=ft.icons.SEARCH,
        dense=True,
        border_radius=10,
    )
    recipients_list = ft.ListView(expand=True, spacing=6)

    def apply_recipient(item: dict):
        tf_template.value = item.get("template", item.get("name", ""))
        dd_rec_type.value = item.get("recipient_type", "ФИЗ. ЛИЦО")
        tf_rec_fio.value = item.get("name", "")
        tf_rec_phone.value = item.get("phone", "")
        tf_rec_email.value = item.get("email", "")
        tf_city_to.value = item.get("city_to", "")
        tf_pvz.value = item.get("pvz_address", "")
        dd_delivery_to.value = item.get("delivery_to", "В ПВЗ")
        dd_tariff.value = item.get("tariff", "Экспресс дверь-склад")
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
                    bgcolor="#1b2333",
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=10, vertical=8),
                    content=ft.Row(
                        [
                            ft.Icon(ft.icons.PERSON, size=18, color="#f59e0b"),
                            ft.Column(
                                [
                                    ft.Text(item.get("name", ""), size=13, weight=ft.FontWeight.W_500),
                                    ft.Text(item.get("city_to", ""), size=11, color="#64748b"),
                                ],
                                spacing=1,
                                expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.icons.CLOSE,
                                icon_size=16,
                                icon_color="#64748b",
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

    def save_current_to_base(_):
        name = tf_rec_fio.value.strip()
        if not name:
            add_log("Введи ФИО получателя, чтобы сохранить в базу.")
            return
        new_item = {
            "name": name,
            "template": tf_template.value.strip(),
            "recipient_type": dd_rec_type.value,
            "phone": tf_rec_phone.value.strip(),
            "email": tf_rec_email.value.strip(),
            "city_to": tf_city_to.value.strip(),
            "pvz_address": tf_pvz.value.strip(),
            "delivery_to": dd_delivery_to.value,
            "tariff": dd_tariff.value,
        }
        nonlocal recipients
        recipients = [r for r in recipients if r.get("name") != name]
        recipients.insert(0, new_item)
        save_recipients(recipients)
        refresh_recipients()
        add_log(f"Сохранено в справочник: {name}")

    tf_search.on_change = refresh_recipients
    recipients_header = ft.Text(f"Справочник получателей ({len(recipients)})", size=15, weight=ft.FontWeight.BOLD)

    # --- ЗАПУСК ОФОРМЛЕНИЯ ---
    btn_run = ft.ElevatedButton(
        text="ОФОРМИТЬ И РАСПЕЧАТАТЬ НАКЛАДНУЮ",
        icon=ft.icons.LOCAL_SHIPPING,
        bgcolor="#f59e0b",
        color="#0f141e",
        height=48,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=10),
            text_style=ft.TextStyle(weight=ft.FontWeight.BOLD, size=14),
        ),
        expand=True,
    )

    def on_run_click(_):
        btn_run.disabled = True
        btn_run.text = "ОФОРМЛЕНИЕ В ПРОЦЕССЕ..."
        log_view.controls.clear()
        page.update()

        order_payload = {
            "login": tf_login.value,
            "password": tf_password.value,
            "template": tf_template.value,
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
            "pvz_address": tf_pvz.value,
            "order_comment": tf_order_comment.value,
            "auto_submit": cb_auto_submit.value,
        }

        def worker():
            try:
                run_cdek_order(order_payload, add_log)
            except Exception as exc:
                add_log(f"[ОШИБКА]: {exc}")
            finally:
                btn_run.disabled = False
                btn_run.text = "ОФОРМИТЬ И РАСПЕЧАТАТЬ НАКЛАДНУЮ"
                refresh_history()
                page.update()

        threading.Thread(target=worker, daemon=True).start()

    btn_run.on_click = on_run_click

    # --- ВСПОМОГАТЕЛЬНАЯ КАРТОЧКА ---
    def section_card(title: str, controls: list):
        return ft.Container(
            bgcolor="#161d2b",
            border_radius=12,
            padding=14,
            border=ft.border.all(1, "#232e42"),
            content=ft.Column(
                [ft.Text(title, size=14, weight=ft.FontWeight.BOLD, color="#f8fafc"), *controls],
                spacing=10,
            ),
        )

    # --- ВКЛАДКА 1: ОФОРМЛЕНИЕ ---
    order_tab = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        spacing=12,
        controls=[
            ft.Container(
                bgcolor="#161d2b",
                border_radius=12,
                padding=14,
                border=ft.border.all(1, "#232e42"),
                content=ft.Row(
                    [
                        ft.Icon(ft.icons.LOCAL_SHIPPING, color="#f59e0b", size=28),
                        ft.Column(
                            [
                                ft.Text('ООО «ЭЛЕКТРОКОННЕКТ» — СДЭК', size=17, weight=ft.FontWeight.BOLD),
                                ft.Text("ИНН 5408154542 • lk.cdek.ru • Автопечать SumatraPDF", size=12, color="#94a3b8"),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.OutlinedButton("+ В базу", icon=ft.icons.PERSON_ADD, on_click=save_current_to_base),
                    ]
                ),
            ),
            section_card(
                "1. О заказе и доступ",
                [
                    ft.Row([tf_login, tf_password]),
                    ft.Row([tf_template, dd_role, dd_payer]),
                    ft.Row([tf_cost_center, tf_city_from, tf_city_to]),
                ],
            ),
            section_card(
                "2. Отправитель и Получатель",
                [
                    ft.Row([tf_sender_company, tf_sender_fio, tf_sender_phone]),
                    ft.Divider(height=1, color="#232e42"),
                    ft.Row([dd_rec_type, tf_rec_fio, tf_rec_phone]),
                    ft.Row([tf_rec_email, tf_pvz]),
                ],
            ),
            section_card(
                "3. Товары, Тариф и Доп. услуги",
                [
                    ft.Row([tf_weight, tf_length, tf_width, tf_height, tf_desc]),
                    ft.Row([dd_pickup_from, dd_delivery_to, dd_tariff]),
                    ft.Row([cb_insurance, tf_declared], alignment=ft.MainAxisAlignment.START),
                ],
            ),
            section_card(
                "4. Забор курьером и Комментарий",
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
                            ft.OutlinedButton("14:00-18:00", on_click=lambda _: set_interval("14:00", "18:00")),
                        ],
                        wrap=True,
                    ),
                    ft.Row([tf_order_comment]),
                    cb_auto_submit,
                    ft.Row([btn_run]),
                    ft.Container(
                        bgcolor="#0b0f17",
                        border_radius=8,
                        padding=8,
                        content=log_view,
                    ),
                ],
            ),
        ],
    )

    # --- ВКЛАДКА 2: ИСТОРИЯ ---
    history_list = ft.ListView(expand=True, spacing=8)

    def refresh_history():
        history_list.controls.clear()
        for h in load_history():
            history_list.controls.append(
                ft.Container(
                    bgcolor="#161d2b",
                    border_radius=10,
                    padding=12,
                    content=ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text(h.get("recipient", ""), weight=ft.FontWeight.BOLD),
                                    ft.Text(
                                        f"{h.get('city_to', '')} • {h.get('tariff', '')} • Забор: {h.get('date', '')}",
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
            ft.Text("История оформленных накладных", size=18, weight=ft.FontWeight.BOLD),
            history_list,
        ],
    )

    # --- ПЕРЕКЛЮЧЕНИЕ ВКЛАДОК ---
    center_container = ft.Container(expand=True, padding=16, content=order_tab)

    def show_order(_):
        center_container.content = order_tab
        page.update()

    def show_history(_):
        refresh_history()
        center_container.content = history_tab
        page.update()

    # Статус SumatraPDF внизу слева
    sumatra_ok = is_sumatra_ready()
    sumatra_badge = ft.Container(
        bgcolor="#0f2922" if sumatra_ok else "#2d1b1b",
        border_radius=8,
        padding=10,
        content=ft.Row(
            [
                ft.Icon(
                    ft.icons.PRINT,
                    size=16,
                    color="#10b981" if sumatra_ok else "#ef4444",
                ),
                ft.Text(
                    "Автопечать SumatraPDF готова" if sumatra_ok else "SumatraPDF.exe не найден",
                    size=11,
                    color="#10b981" if sumatra_ok else "#ef4444",
                ),
            ]
        ),
    )

    left_sidebar = ft.Container(
        width=230,
        bgcolor="#131926",
        padding=14,
        border=ft.border.only(right=ft.BorderSide(1, "#232e42")),
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.icons.LOCAL_SHIPPING, color="#10b981", size=26),
                        ft.Column(
                            [
                                ft.Text("СДЭК", weight=ft.FontWeight.BOLD, size=15),
                                ft.Text("Выписка накладных", size=11, color="#64748b"),
                            ],
                            spacing=0,
                        ),
                    ]
                ),
                ft.Divider(color="#232e42"),
                ft.ListTile(
                    leading=ft.Icon(ft.icons.EDIT_DOCUMENT, color="#f59e0b"),
                    title=ft.Text("Электроконнект", size=13),
                    subtitle=ft.Text("Оформление СДЭК", size=11),
                    on_click=show_order,
                ),
                ft.ListTile(
                    leading=ft.Icon(ft.icons.HISTORY, color="#94a3b8"),
                    title=ft.Text("История", size=13),
                    subtitle=ft.Text("Архив накладных", size=11),
                    on_click=show_history,
                ),
                ft.Container(expand=True),
                sumatra_badge,
            ]
        ),
    )

    right_sidebar = ft.Container(
        width=310,
        bgcolor="#131926",
        padding=14,
        border=ft.border.only(left=ft.BorderSide(1, "#232e42")),
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
