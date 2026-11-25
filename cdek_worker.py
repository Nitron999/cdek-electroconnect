import os
import time
from typing import Callable
from playwright.sync_api import sync_playwright, Page
from storage import DOWNLOADS_DIR, add_history_entry
from printer import print_pdf_silent

CDEK_URL = "https://lk.cdek.ru/"
CDEK_CREATE_URL = "https://lk.cdek.ru/order/create"


def _safe_fill(page: Page, selectors: list[str], value: str, clear: bool = True) -> bool:
    if not value:
        return False
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=1500):
                loc.click()
                if clear:
                    loc.press("ControlOrMeta+A")
                    loc.press("Backspace")
                loc.fill(str(value))
                return True
        except Exception:
            continue
    return False


def _safe_click_text(page: Page, text: str, timeout: int = 2500) -> bool:
    if not text:
        return False
    try:
        loc = page.get_by_text(text, exact=False).first
        loc.click(timeout=timeout)
        return True
    except Exception:
        return False


def _fill_autocomplete(page: Page, selectors: list[str], value: str) -> bool:
    if _safe_fill(page, selectors, value):
        page.wait_for_timeout(1200)
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
        page.wait_for_timeout(500)
        return True
    return False


def run_cdek_order(order: dict, log: Callable[[str], None]) -> None:
    """Выполняет оформление заказа в lk.cdek.ru и печатает накладную через SumatraPDF."""
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
            log("2. Открываю lk.cdek.ru и выполняю вход...")
            page.goto(CDEK_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1500)

            _safe_fill(
                page,
                [
                    "input[name='login']",
                    "input[name='username']",
                    "input[type='text']",
                    "input[placeholder*='Логин' i]",
                ],
                login,
            )
            _safe_fill(
                page,
                [
                    "input[name='password']",
                    "input[type='password']",
                    "input[placeholder*='Пароль' i]",
                ],
                password,
            )
            page.keyboard.press("Enter")
            _safe_click_text(page, "Войти", timeout=2000)

            log("-> Ожидаю входа в личный кабинет (если есть капча — реши её в браузере)...")
            page.wait_for_function(
                "() => !window.location.href.includes('login') && !window.location.href.includes('auth')",
                timeout=180000,
            )
            page.wait_for_timeout(1500)

            log("3. Перехожу на страницу создания заказа...")
            page.goto(CDEK_CREATE_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)

            # --- БЛОК 1: О ЗАКАЗЕ ---
            log("4. Заполняю блок «О заказе»...")
            if order.get("template"):
                _fill_autocomplete(
                    page,
                    [
                        "input[placeholder*='Шаблон' i]",
                        "label:has-text('Шаблон заказа') >> .. >> input",
                    ],
                    order["template"],
                )
                page.wait_for_timeout(1200)

            _safe_click_text(page, order.get("role", "ОТПРАВИТЕЛЕМ"))
            _safe_click_text(page, order.get("payer", "ПО ДОГОВОРУ"))

            if order.get("city_from"):
                _fill_autocomplete(
                    page,
                    [
                        "label:has-text('Город отправителя') >> .. >> input",
                        "input[placeholder*='Город отправителя' i]",
                    ],
                    order["city_from"],
                )

            if order.get("city_to"):
                _fill_autocomplete(
                    page,
                    [
                        "label:has-text('Город получателя') >> .. >> input",
                        "input[placeholder*='Город получателя' i]",
                    ],
                    order["city_to"],
                )

            # --- БЛОК 2: ОТПРАВИТЕЛЬ ---
            log("5. Заполняю блок «Отправитель»...")
            sender_section = page.locator("section, div").filter(has_text="Отправитель").first
            try:
                if order.get("sender_fio"):
                    sender_section.locator("input").nth(2).fill(order["sender_fio"])
                if order.get("sender_phone"):
                    sender_section.locator("input").nth(3).fill(order["sender_phone"])
            except Exception:
                pass

            # --- БЛОК 3: ПОЛУЧАТЕЛЬ ---
            log("6. Заполняю блок «Получатель»...")
            _safe_click_text(page, order.get("recipient_type", "ФИЗ. ЛИЦО"))
            _safe_fill(
                page,
                [
                    "label:has-text('ФИО') >> nth=1 >> .. >> input",
                    "input[name*='recipient'][name*='name' i]",
                ],
                order.get("recipient_fio", ""),
            )
            _safe_fill(
                page,
                [
                    "label:has-text('Телефон') >> nth=1 >> .. >> input",
                    "input[name*='recipient'][name*='phone' i]",
                ],
                order.get("recipient_phone", ""),
            )
            if order.get("recipient_email"):
                _safe_fill(
                    page,
                    ["input[type='email']", "input[placeholder*='почта' i]"],
                    order["recipient_email"],
                )

            # --- БЛОК 4: ТОВАРЫ ---
            log("7. Заполняю габариты и описание груза...")
            _safe_fill(page, ["label:has-text('Вес') >> .. >> input"], order.get("weight", "0.5"))
            _safe_fill(page, ["label:has-text('Длина') >> .. >> input"], order.get("length", "10"))
            _safe_fill(page, ["label:has-text('Ширина') >> .. >> input"], order.get("width", "10"))
            _safe_fill(page, ["label:has-text('Высота') >> .. >> input"], order.get("height", "5"))
            _safe_fill(
                page,
                [
                    "label:has-text('Описание груза') >> .. >> input",
                    "input[placeholder*='Описание' i]",
                ],
                order.get("description", "ПЛАТЫ"),
            )

            # --- БЛОК 5: ТАРИФЫ ---
            log("8. Выбираю тариф...")
            _safe_click_text(page, order.get("pickup_from", "КУРЬЕР ЗАБЕРЁТ ПО АДРЕСУ"))
            _safe_click_text(page, order.get("delivery_to", "В ПВЗ"))
            page.wait_for_timeout(1500)
            _safe_click_text(page, order.get("tariff", "Экспресс дверь-склад"), timeout=4000)

            # --- БЛОК 6: ДОПОЛНИТЕЛЬНЫЕ УСЛУГИ ---
            if order.get("use_insurance") and order.get("declared_value"):
                log("9. Указываю объявленную стоимость...")
                _safe_click_text(page, "Дополнительный сбор за объявленную стоимость", timeout=2500)
                _safe_fill(
                    page,
                    [
                        "input[placeholder*='объявленная стоимость' i]",
                        "label:has-text('объявленная стоимость') >> .. >> input",
                    ],
                    order["declared_value"],
                )

            # --- БЛОК 7: ИНФОРМАЦИЯ ОБ ОТПРАВЛЕНИИ ---
            log("10. Заполняю адрес, дату и время забора...")
            _safe_fill(
                page,
                [
                    "label:has-text('Адрес') >> .. >> input",
                    "input[placeholder*='Адрес' i]",
                ],
                order.get("pickup_address", "Шоссейная 21, офис 426"),
            )
            if order.get("courier_comment"):
                _safe_fill(
                    page,
                    ["label:has-text('Комментарий для курьера') >> .. >> input"],
                    order["courier_comment"],
                )
            _safe_fill(
                page,
                ["label:has-text('Дата и время забора') >> .. >> input"],
                order.get("pickup_date", ""),
            )
            if order.get("time_from"):
                _safe_click_text(page, order["time_from"], timeout=1500)
            if order.get("time_to"):
                _safe_click_text(page, order["time_to"], timeout=1500)

            if order.get("need_attorney"):
                _safe_click_text(page, "Курьеру необходима доверенность", timeout=1500)
            if order.get("need_id_doc"):
                _safe_click_text(page, "Курьеру необходим документ удостоверяющий личность", timeout=1500)

            # --- ВЫБОР ПВЗ ИЛИ ПОСТАМАТА ---
            pvz_query = (order.get("pvz_code") or order.get("pvz_address") or "").strip()
            if pvz_query and order.get("delivery_to") in ("В ПВЗ", "В ПОСТАМАТ"):
                log(f"11. Выбираю ПВЗ/постамат: {pvz_query}...")
                # Если ПВЗ уже выбран из шаблона — жмём ИЗМЕНИТЬ
                _safe_click_text(page, "ИЗМЕНИТЬ", timeout=1500)
                page.wait_for_timeout(800)

                if _safe_fill(
                    page,
                    [
                        "input[placeholder*='Поиск по ПВЗ' i]",
                        "input[placeholder*='постамат' i]",
                    ],
                    pvz_query,
                ):
                    page.wait_for_timeout(1500)
                    # Кликаем по найденному пункту в списке слева от карты
                    if not _safe_click_text(page, pvz_query, timeout=3000):
                        if order.get("pvz_address"):
                            _safe_click_text(page, order["pvz_address"], timeout=3000)
                    page.wait_for_timeout(800)
                    _safe_click_text(page, "Выбрать", timeout=2000)

            # --- КОММЕНТАРИЙ К ЗАКАЗУ ---
            log("12. Заполняю комментарий к заказу...")
            if order.get("order_comment"):
                _safe_fill(
                    page,
                    [
                        "textarea",
                        "label:has-text('Комментарий к заказу') >> .. >> textarea",
                    ],
                    order["order_comment"],
                )

            # --- СОЗДАНИЕ ЗАКАЗА ---
            log("13. Нажимаю «СОЗДАТЬ ЗАКАЗ»...")
            _safe_click_text(page, "СОЗДАТЬ ЗАКАЗ", timeout=5000)

            # --- ПЕРЕХВАТ СКАЧИВАНИЯ PDF И АВТОПЕЧАТЬ ---
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
