import os
import re
import time
from typing import Callable
from playwright.sync_api import sync_playwright, Page
from storage import DOWNLOADS_DIR, add_history_entry
from printer import print_pdf_silent

CDEK_URL = "https://lk.cdek.ru/"


def _section_prefix(section_title: str) -> list[str]:
    """Возвращает XPath-префиксы заголовка секции (минуя левое меню навигации)."""
    return [
        f"//*[self::h1 or self::h2 or self::h3 or self::h4][normalize-space(text())='{section_title}']",
        f"(//*[normalize-space(text())='{section_title}'])[last()]",
    ]


def _fill_locator(loc, value: str, clear: bool = True) -> bool:
    try:
        loc.scroll_into_view_if_needed(timeout=2000)
        if not loc.is_visible(timeout=1500):
            return False
        loc.click()
        if clear:
            loc.press("ControlOrMeta+A")
            loc.press("Backspace")
        loc.fill(str(value))
        return True
    except Exception:
        return False


def _fill_after_label(
    page: Page,
    field_text: str,
    value: str,
    section_title: str | None = None,
    tag: str = "input",
) -> bool:
    """Находит первое активное поле ввода строго после подписи field_text (внутри указанной секции)."""
    if not value:
        return False

    cond = "not(@type='hidden') and not(@disabled) and not(@readonly)" if tag == "input" else "not(@disabled)"
    xpaths = []
    if section_title:
        for pref in _section_prefix(section_title):
            xpaths.append(f"xpath={pref}/following::*[contains(text(), '{field_text}')][1]/following::{tag}[{cond}][1]")
    else:
        xpaths.append(f"xpath=//*[contains(text(), '{field_text}')][1]/following::{tag}[{cond}][1]")

    for xp in xpaths:
        if _fill_locator(page.locator(xp).first, value):
            return True
    return False


def _fill_phone_in_section(page: Page, section_title: str, phone: str) -> bool:
    """Аккуратно заполняет телефон с учётом маски +7 в СДЭК."""
    if not phone:
        return False
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 11 and digits[0] in ("7", "8"):
        formatted = f"+7{digits[1:]}"
        short10 = digits[1:]
    elif len(digits) == 10:
        formatted = f"+7{digits}"
        short10 = digits
    else:
        formatted = phone
        short10 = phone

    for pref in _section_prefix(section_title):
        xp = f"xpath={pref}/following::*[contains(text(), 'Телефон')][1]/following::input[not(@type='hidden') and not(@disabled)][1]"
        loc = page.locator(xp).first
        try:
            loc.scroll_into_view_if_needed(timeout=2000)
            if not loc.is_visible(timeout=1500):
                continue
            loc.click()
            loc.press("ControlOrMeta+A")
            loc.press("Backspace")
            # Если поле само держит префикс +7 — вводим 10 цифр, иначе полный номер
            current = (loc.input_value() or "").strip()
            if current.startswith("+7"):
                loc.type(short10, delay=30)
            else:
                loc.fill(formatted)
            return True
        except Exception:
            continue
    return False


def _click_in_section(page: Page, section_title: str, button_text: str, timeout: int = 2500) -> bool:
    if not button_text:
        return False
    for pref in _section_prefix(section_title):
        xp = f"xpath={pref}/following::*[contains(normalize-space(text()), '{button_text}')][1]"
        try:
            loc = page.locator(xp).first
            loc.scroll_into_view_if_needed(timeout=1500)
            loc.click(timeout=timeout)
            return True
        except Exception:
            continue
    return False


def _safe_click_text(page: Page, text: str, timeout: int = 2500, exact: bool = False) -> bool:
    if not text:
        return False
    try:
        loc = page.get_by_text(text, exact=exact).first
        loc.scroll_into_view_if_needed(timeout=1500)
        loc.click(timeout=timeout)
        return True
    except Exception:
        return False


def _fill_city_field(page: Page, field_label: str, city_value: str, use_moscow_quicklink: bool = False) -> bool:
    """Заполняет поле города отправителя или получателя и выбирает город из выпадающего списка."""
    if not city_value:
        return False

    # Для города отправителя «Москва» — пробуем быструю ссылку «Москва» прямо под полем
    if use_moscow_quicklink and "москва" in city_value.lower():
        try:
            quick = page.locator(
                f"xpath=//*[contains(text(), '{field_label}')]/following::*[normalize-space(text())='Москва'][1]"
            ).first
            if quick.is_visible(timeout=2000):
                quick.click()
                page.wait_for_timeout(700)
                inp = page.locator(
                    f"xpath=//*[contains(text(), '{field_label}')]/following::input[not(@type='hidden') and not(@disabled)][1]"
                ).first
                if "москва" in (inp.input_value() or "").lower():
                    return True
        except Exception:
            pass

    # Основной способ: ввод города в конкретное поле + выбор из подсказок
    inp = page.locator(
        f"xpath=//*[contains(text(), '{field_label}')]/following::input[not(@type='hidden') and not(@disabled)][1]"
    ).first
    city_short = city_value.split(",")[0].strip()
    if _fill_locator(inp, city_short):
        page.wait_for_timeout(1400)
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
        page.wait_for_timeout(700)
        return True
    return False


def run_cdek_order(order: dict, log: Callable[[str], None]) -> None:
    """Всегда создаёт новый заказ в lk.cdek.ru с нуля, заполняет все поля по секциям и печатает через SumatraPDF."""
    login = order.get("login", "").strip()
    password = order.get("password", "").strip()

    with sync_playwright() as p:
        log("1. Запускаю браузер...")
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--no-sandbox",
        ]
        try:
            browser = p.chromium.launch(
                channel="chrome",
                headless=False,
                slow_mo=80,
                args=launch_args,
            )
        except Exception:
            browser = p.chromium.launch(
                headless=False,
                slow_mo=80,
                args=launch_args,
            )

        context = browser.new_context(
            viewport={"width": 1366, "height": 860},
            accept_downloads=True,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = context.new_page()

        try:
            # --- ШАГ 1: ВХОД (зелёная кнопка ВОЙТИ) ---
            log("2. Открываю lk.cdek.ru и ввожу логин/пароль...")
            page.goto(CDEK_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1500)

            _fill_locator(page.locator("input[type='text'], input[name='login'], input[name='username']").first, login)
            _fill_locator(page.locator("input[type='password'], input[name='password']").first, password)
            page.wait_for_timeout(400)

            log("-> Нажимаю зелёную кнопку «ВОЙТИ»...")
            clicked_login = False
            try:
                page.get_by_role("button", name="ВОЙТИ", exact=True).click(timeout=3000)
                clicked_login = True
            except Exception:
                pass
            if not clicked_login:
                clicked_login = _safe_click_text(page, "ВОЙТИ", timeout=2500, exact=True)
            if not clicked_login:
                page.keyboard.press("Enter")

            log("-> Жду загрузку кабинета (если есть капча — реши её в браузере)...")
            page.wait_for_selector("text=Новый заказ", timeout=180000)
            page.wait_for_timeout(1000)

            # --- ШАГ 2: КЛИК «Новый заказ» ---
            log("3. Открываю «Новый заказ»...")
            try:
                page.get_by_role("link", name="Новый заказ", exact=True).first.click(timeout=4000)
            except Exception:
                if not _safe_click_text(page, "Новый заказ", timeout=4000, exact=True):
                    _safe_click_text(page, "НОВЫЙ ЗАКАЗ", timeout=4000)

            page.wait_for_selector("text=О заказе", timeout=30000)
            page.wait_for_timeout(1500)

            # --- ШАГ 3: БЛОК «О ЗАКАЗЕ» ---
            log("4. Заполняю блок «О заказе» (Отправитель: Москва -> Город получателя)...")
            _click_in_section(page, "О заказе", order.get("role", "ОТПРАВИТЕЛЕМ"))
            _click_in_section(page, "О заказе", order.get("payer", "ПО ДОГОВОРУ"))
            page.wait_for_timeout(400)

            # Город отправителя — всегда Москва
            _fill_city_field(page, "Город отправителя", "Москва", use_moscow_quicklink=True)

            # Город получателя — из базы / введённый в программе
            if order.get("city_to"):
                _fill_city_field(page, "Город получателя", order["city_to"], use_moscow_quicklink=False)

            # --- ШАГ 4: БЛОК «ОТПРАВИТЕЛЬ» (Крылова Людмила Борисовна и её телефон) ---
            log("5. Заполняю контактное лицо отправителя (Крылова)...")
            _fill_after_label(page, "ФИО", order.get("sender_fio", "Крылова Людмила Борисовна"), section_title="Отправитель")
            _fill_phone_in_section(page, "Отправитель", order.get("sender_phone", "+7 916 195 36 94"))

            # --- ШАГ 5: БЛОК «ПОЛУЧАТЕЛЬ» (из базы / программы) ---
            log("6. Заполняю блок «Получатель»...")
            rec_type = order.get("recipient_type", "ФИЗ. ЛИЦО")
            _click_in_section(page, "Получатель", rec_type)
            page.wait_for_timeout(500)

            if rec_type == "ЮР. ЛИЦО":
                # Если выбрано ЮР. ЛИЦО, заполняем также наименование компании, если поле появилось
                _fill_after_label(page, "Наименование", order.get("recipient_fio", ""), section_title="Получатель")

            _fill_after_label(page, "ФИО", order.get("recipient_fio", ""), section_title="Получатель")
            _fill_phone_in_section(page, "Получатель", order.get("recipient_phone", ""))
            if order.get("recipient_email"):
                _fill_after_label(page, "Электронная почта", order["recipient_email"], section_title="Получатель")

            # --- ШАГ 6: БЛОК «ТОВАРЫ» (Вес, Длина, Ширина, Высота, Описание груза) ---
            log("7. Заполняю товары (вес, габариты, описание груза)...")
            _fill_after_label(page, "Вес", order.get("weight", "0.5"), section_title="Товары")
            _fill_after_label(page, "Длина", order.get("length", "10"), section_title="Товары")
            _fill_after_label(page, "Ширина", order.get("width", "10"), section_title="Товары")
            _fill_after_label(page, "Высота", order.get("height", "5"), section_title="Товары")
            _fill_after_label(page, "Описание груза", order.get("description", "ПЛАТЫ"), section_title="Товары")
            page.wait_for_timeout(1000)

            # --- ШАГ 7: БЛОК «ТАРИФЫ» ---
            log("8. Выбираю тариф...")
            _click_in_section(page, "Тарифы", order.get("pickup_from", "КУРЬЕР ЗАБЕРЁТ ПО АДРЕСУ"))
            _click_in_section(page, "Тарифы", order.get("delivery_to", "В ПВЗ"))
            page.wait_for_timeout(2000)
            _click_in_section(page, "Тарифы", order.get("tariff", "Экспресс дверь-склад"), timeout=4000)
            page.wait_for_timeout(800)

            # --- ШАГ 8: ДОПОЛНИТЕЛЬНЫЕ УСЛУГИ ---
            if order.get("use_insurance") and order.get("declared_value"):
                log("9. Указываю объявленную стоимость...")
                _click_in_section(page, "Дополнительные услуги", "Дополнительный сбор за объявленную стоимость")
                page.wait_for_timeout(400)
                _fill_after_label(
                    page,
                    "объявленная стоимость",
                    order["declared_value"],
                    section_title="Дополнительные услуги",
                )

            # --- ШАГ 9: ИНФОРМАЦИЯ ОБ ОТПРАВЛЕНИИ (ЗАБОР КУРЬЕРОМ) ---
            log("10. Заполняю адрес, дату и время забора...")
            _fill_after_label(
                page,
                "Адрес",
                order.get("pickup_address", "Сущёвская, 21, офис 426"),
                section_title="Информация об отправлении",
            )
            if order.get("courier_comment"):
                _fill_after_label(
                    page,
                    "Комментарий для курьера",
                    order["courier_comment"],
                    section_title="Информация об отправлении",
                )
            _fill_after_label(
                page,
                "Дата и время забора",
                order.get("pickup_date", ""),
                section_title="Информация об отправлении",
            )
            if order.get("time_from"):
                _click_in_section(page, "Информация об отправлении", order["time_from"], timeout=1500)
            if order.get("time_to"):
                _click_in_section(page, "Информация об отправлении", order["time_to"], timeout=1500)

            if order.get("need_attorney"):
                _click_in_section(page, "Информация об отправлении", "Курьеру необходима доверенность", timeout=1500)
            if order.get("need_id_doc"):
                _click_in_section(
                    page,
                    "Информация об отправлении",
                    "Курьеру необходим документ удостоверяющий личность",
                    timeout=1500,
                )

            # --- ШАГ 10: ПВЗ / ПОСТАМАТ ИЛИ ДОСТАВКА КУРЬЕРОМ ---
            delivery_to = order.get("delivery_to", "В ПВЗ")
            pvz_query = (order.get("pvz_code") or order.get("pvz_address") or "").strip()

            if delivery_to in ("В ПВЗ", "В ПОСТАМАТ") and pvz_query:
                log(f"11. Выбираю ПВЗ/постамат: {pvz_query}...")
                _click_in_section(page, "Информация об отправлении", "ИЗМЕНИТЬ", timeout=1500)
                page.wait_for_timeout(800)

                pvz_inp = page.locator("input[placeholder*='Поиск по ПВЗ' i], input[placeholder*='постамат' i]").first
                if _fill_locator(pvz_inp, pvz_query):
                    page.wait_for_timeout(1500)
                    if not _safe_click_text(page, pvz_query, timeout=3000):
                        if order.get("pvz_address"):
                            _safe_click_text(page, order["pvz_address"], timeout=3000)
                    page.wait_for_timeout(800)
                    _safe_click_text(page, "Выбрать", timeout=2000)
            elif delivery_to == "КУРЬЕРОМ ПО АДРЕСУ" and order.get("pvz_address"):
                log(f"11. Заполняю адрес доставки курьером: {order['pvz_address']}...")
                _fill_after_label(page, "Улица", order["pvz_address"], section_title="Информация об отправлении")

            # --- ШАГ 11: КОММЕНТАРИЙ К ЗАКАЗУ ---
            log("12. Заполняю комментарий к заказу...")
            if order.get("order_comment"):
                _fill_after_label(
                    page,
                    "Комментарий к заказу",
                    order["order_comment"],
                    tag="textarea",
                )

            # --- ШАГ 12: СОЗДАНИЕ ЗАКАЗА ---
            log("13. Нажимаю «СОЗДАТЬ ЗАКАЗ»...")
            _safe_click_text(page, "СОЗДАТЬ ЗАКАЗ", timeout=5000)

            # --- ШАГ 13: СКАЧИВАНИЕ PDF И АВТОПЕЧАТЬ SUMATRAPDF ---
            log("14. Жду формирование PDF-накладной для автопечати...")
            pdf_path = None
            try:
                with page.expect_download(timeout=180000) as download_info:
                    for _ in range(15):
                        if (
                            _safe_click_text(page, "Печать квитанции", timeout=1500)
                            or _safe_click_text(page, "Распечатать", timeout=1500)
                            or _safe_click_text(page, "Печать", timeout=1500)
                        ):
                            break
                        page.wait_for_timeout(1500)

                download = download_info.value
                filename = f"cdek_{int(time.time())}_{download.suggested_filename}"
                pdf_path = os.path.join(DOWNLOADS_DIR, filename)
                download.save_as(pdf_path)
                log(f"-> Накладная сохранена: {filename}")
            except Exception as e:
                log(f"[ВНИМАНИЕ] PDF не перехвачен автоматически: {e}")

            if pdf_path:
                ok, msg = print_pdf_silent(pdf_path)
                log(f"-> {msg}")
                add_history_entry(
                    {
                        "recipient": order.get("recipient_fio", ""),
                        "city_to": order.get("city_to", ""),
                        "date": order.get("pickup_date", ""),
                        "tariff": order.get("tariff", ""),
                        "pvz": pvz_query,
                        "pdf": os.path.basename(pdf_path),
                        "printed": ok,
                    }
                )

            log("ГОТОВО! Заказ оформлен.")
            page.wait_for_timeout(4000)
        finally:
            browser.close()
