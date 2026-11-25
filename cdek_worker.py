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
        f"//*[self::h1 or self::h2 or self::h3 or self::h4][normalize-space(.)='{section_title}']",
        f"(//*[normalize-space(.)='{section_title}'])[last()]",
    ]


def _fill_locator(loc, value: str, clear: bool = True, press_tab: bool = False) -> bool:
    try:
        loc.scroll_into_view_if_needed(timeout=2000)
        if not loc.is_visible(timeout=1500):
            return False
        loc.click()
        if clear:
            loc.press("ControlOrMeta+A")
            loc.press("Backspace")
        loc.fill(str(value))
        if press_tab:
            loc.press("Tab")
        return True
    except Exception:
        return False


def _fill_after_label(
    page: Page,
    field_text: str,
    value: str,
    section_title: str | None = None,
    tag: str = "input",
    press_tab: bool = False,
) -> bool:
    """Находит первое активное поле ввода строго после подписи field_text (с учётом переносов строк)."""
    if not value:
        return False

    cond = (
        "not(@type='hidden') and not(@type='checkbox') and not(@type='radio') and not(@disabled) and not(@readonly)"
        if tag == "input"
        else "not(@disabled)"
    )
    xpaths = []
    if section_title:
        for pref in _section_prefix(section_title):
            xpaths.append(
                f"xpath={pref}/following::*[contains(normalize-space(.), '{field_text}') and not(descendant::input)][1]/following::{tag}[{cond}][1]"
            )
            xpaths.append(
                f"xpath={pref}/following::*[contains(text(), '{field_text}')][1]/following::{tag}[{cond}][1]"
            )
    else:
        xpaths.append(
            f"xpath=//*[contains(normalize-space(.), '{field_text}') and not(descendant::input)][1]/following::{tag}[{cond}][1]"
        )
        xpaths.append(f"xpath=//*[contains(text(), '{field_text}')][1]/following::{tag}[{cond}][1]")

    for xp in xpaths:
        if _fill_locator(page.locator(xp).first, value, press_tab=press_tab):
            return True
    return False


def _fill_cargo_description(page: Page, description: str, log: Callable[[str], None]) -> bool:
    """Железобетонно заполняет '* Описание груза' (и input, и textarea)."""
    desc = (description or "ПЛАТЫ").strip()

    try:
        found = page.evaluate(
            """() => {
                const all = Array.from(document.querySelectorAll('*'));
                const labelEl = all.find(el => {
                    if (el.children.length > 2) return false;
                    const t = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                    return t.includes('описание') && t.includes('груза');
                });
                if (!labelEl) return false;

                let parent = labelEl.parentElement;
                for (let i = 0; i < 5 && parent; i++) {
                    const field = parent.querySelector('input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]):not([disabled]), textarea:not([disabled])');
                    if (field && field.offsetParent !== null) {
                        field.scrollIntoView({block: 'center'});
                        field.focus();
                        field.click();
                        return true;
                    }
                    parent = parent.parentElement;
                }
                return false;
            }"""
        )
        if found:
            page.wait_for_timeout(200)
            page.keyboard.press("ControlOrMeta+A")
            page.keyboard.press("Backspace")
            page.keyboard.type(desc, delay=35)
            page.keyboard.press("Tab")
            page.wait_for_timeout(400)
            log(f"-> Описание груза вписано: {desc}")
            return True
    except Exception:
        pass

    try:
        for _ in range(5):
            page.keyboard.press("Tab")
            page.wait_for_timeout(150)
            is_target = page.evaluate(
                """() => {
                    const el = document.activeElement;
                    if (!el) return false;
                    const tag = el.tagName;
                    if (tag !== 'INPUT' && tag !== 'TEXTAREA') return false;
                    const t = (el.type || '').toLowerCase();
                    if (t === 'checkbox' || t === 'radio' || t === 'button') return false;
                    return (el.value || '').trim() === '';
                }"""
            )
            if is_target:
                page.keyboard.type(desc, delay=35)
                page.keyboard.press("Tab")
                page.wait_for_timeout(400)
                log(f"-> Описание груза вписано (через Tab): {desc}")
                return True
    except Exception:
        pass

    for tag in ("input", "textarea"):
        if _fill_after_label(page, "Описание", desc, section_title="Товары", tag=tag, press_tab=True):
            log(f"-> Описание груза вписано ({tag}): {desc}")
            return True

    log("[ВНИМАНИЕ] Не удалось найти поле «Описание груза»!")
    return False


def _fill_declared_value(page: Page, value: str, log: Callable[[str], None]) -> bool:
    """Заполняет 'Дополнительный сбор за объявленную стоимость'."""
    val = str(value or "").strip()
    if not val:
        return False

    try:
        focused = page.evaluate(
            """() => {
                const all = Array.from(document.querySelectorAll('*'));
                const titleEl = all.find(el => {
                    if (el.children.length > 2) return false;
                    const t = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                    return t.includes('дополнительный сбор за объявленную стоимость');
                });
                if (!titleEl) return false;

                let box = titleEl.parentElement;
                for (let i = 0; i < 6 && box; i++) {
                    const inp = box.querySelector('input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"])');
                    if (inp && inp.offsetParent !== null) {
                        if (inp.disabled) {
                            const cb = box.querySelector('input[type="checkbox"], [role="checkbox"]');
                            if (cb) cb.click();
                        }
                        inp.scrollIntoView({block: 'center'});
                        inp.focus();
                        inp.click();
                        return true;
                    }
                    box = box.parentElement;
                }
                return false;
            }"""
        )
        if focused:
            page.wait_for_timeout(250)
            page.keyboard.press("ControlOrMeta+A")
            page.keyboard.press("Backspace")
            page.keyboard.type(val, delay=35)
            page.keyboard.press("Tab")
            page.wait_for_timeout(400)
            log(f"-> Объявленная стоимость вписана: {val}")
            return True
    except Exception:
        pass

    try:
        xp = "xpath=//*[contains(normalize-space(.), 'объявленная стоимость') and not(descendant::input)][1]/preceding::input[not(@type='hidden') and not(@type='checkbox') and not(@disabled)][1]"
        if _fill_locator(page.locator(xp).first, val, press_tab=True):
            log(f"-> Объявленная стоимость вписана (XPath): {val}")
            return True
    except Exception:
        pass

    log("[ВНИМАНИЕ] Не удалось вписать объявленную стоимость!")
    return False


def _select_pickup_time(page: Page, time_from: str, time_to: str, log: Callable[[str], None]) -> None:
    """Выбирает время забора 'с' (12:00) и 'до' (15:00) в полях с иконкой часов (вместо 09:00 - 18:00)."""
    t_from = (time_from or "12:00").strip()
    t_to = (time_to or "15:00").strip()

    def _pick_single_time(slot_idx: int, default_val: str, target_val: str) -> bool:
        if not target_val:
            return False

        # Ищем поле времени: сначала по значению (09:00 / 18:00), затем по позиции после «Дата и время забора»
        opened = False
        try:
            opened = page.evaluate(
                """([slotIdx, defVal]) => {
                    // 1. Поиск input с текущим значением (09:00 или 18:00)
                    const inputs = Array.from(document.querySelectorAll('input:not([type="hidden"]):not([type="checkbox"])'))
                        .filter(el => el.offsetParent !== null && !el.disabled);
                    const byVal = inputs.find(el => (el.value || '').trim() === defVal);
                    if (byVal) {
                        byVal.scrollIntoView({block: 'center'});
                        byVal.click();
                        return true;
                    }
                    // 2. Поиск блока/текста '09:00' или '18:00'
                    const all = Array.from(document.querySelectorAll('div, span, button'));
                    const textEl = all.find(el => el.children.length === 0 && (el.innerText || '').trim() === defVal && el.offsetParent !== null);
                    if (textEl) {
                        textEl.scrollIntoView({block: 'center'});
                        textEl.click();
                        return true;
                    }
                    return false;
                }""",
                [slot_idx, default_val],
            )
        except Exception:
            opened = False

        if not opened:
            # Резерв: XPath после подписи «Дата и время забора» (включая readonly поля!)
            xp = (
                "xpath=//*[contains(normalize-space(.), 'Дата и время забора') and not(descendant::input)][1]"
                f"/following::input[not(@type='hidden') and not(@type='checkbox') and not(@disabled)][{slot_idx}]"
            )
            try:
                loc = page.locator(xp).first
                loc.scroll_into_view_if_needed(timeout=1500)
                if loc.is_visible(timeout=1500):
                    loc.click(force=True)
                    opened = True
            except Exception:
                pass

        if not opened:
            return False

        page.wait_for_timeout(600)

        # Пробуем выбрать нужное время из открывшегося выпадающего списка
        try:
            picked = page.evaluate(
                """(target) => {
                    const els = Array.from(document.querySelectorAll('li, div, span, button, option'));
                    for (let i = els.length - 1; i >= 0; i--) {
                        const el = els[i];
                        if (el.children.length > 1 || el.offsetParent === null) continue;
                        const txt = (el.innerText || el.textContent || '').trim();
                        if (txt === target) {
                            el.scrollIntoView({block: 'nearest'});
                            el.click();
                            return true;
                        }
                    }
                    return false;
                }""",
                target_val,
            )
            if picked:
                page.wait_for_timeout(500)
                return True
        except Exception:
            pass

        # Если список не появился — пробуем ввести время с клавиатуры
        try:
            page.keyboard.press("ControlOrMeta+A")
            page.keyboard.press("Backspace")
            page.keyboard.type(target_val, delay=40)
            page.keyboard.press("Enter")
            page.wait_for_timeout(400)
            return True
        except Exception:
            return False

    ok1 = _pick_single_time(2, "09:00", t_from)
    ok2 = _pick_single_time(3, "18:00", t_to)
    if ok1 or ok2:
        log(f"-> Время забора установлено: {t_from} - {t_to}")
    else:
        log(f"[ВНИМАНИЕ] Не удалось изменить время забора на {t_from} - {t_to}")


def _select_pvz_on_cdek(page: Page, pvz_code: str, pvz_address: str, log: Callable[[str], None]) -> bool:
    """Вписывает код или адрес в 'Поиск по ПВЗ/постамату' прямо на странице и выбирает нужный пункт."""
    code = (pvz_code or "").strip()
    addr = (pvz_address or "").strip()
    if not code and not addr:
        return False

    short_addr = re.sub(
        r"^(ул\.?|улица|пр-т\.?|проспект|б-р\.?|бульвар|ш\.?|шоссе)\s*",
        "",
        addr,
        flags=re.IGNORECASE,
    ).strip()
    query = code if code else short_addr

    log(f"11. Выбираю ПВЗ/постамат: {query}...")

    search_selectors = [
        "input[placeholder*='Поиск по ПВЗ' i]",
        "input[placeholder*='постамат' i]",
        "xpath=//*[contains(normalize-space(.), 'Доставить в ПВЗ')][last()]/following::input[not(@type='hidden') and not(@disabled)][1]",
    ]

    # 1. Сначала проверяем, открыто ли уже поле «Поиск по ПВЗ/постамату» прямо на странице
    search_inp = None
    for sel in search_selectors:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=1200):
                search_inp = loc
                break
        except Exception:
            continue

    # 2. Если поле скрыто (уже выбран какой-то пункт) — жмём «ИЗМЕНИТЬ»
    if search_inp is None:
        for sel in (
            "xpath=//*[contains(normalize-space(.), 'Доставить в ПВЗ')][last()]/following::*[normalize-space(.)='ИЗМЕНИТЬ' or normalize-space(.)='Изменить'][1]",
            "button:has-text('ИЗМЕНИТЬ')",
            "text=ИЗМЕНИТЬ",
        ):
            try:
                btn = page.locator(sel).first
                btn.scroll_into_view_if_needed(timeout=1500)
                if btn.is_visible(timeout=1500):
                    btn.click(force=True, timeout=2500)
                    page.wait_for_timeout(1200)
                    break
            except Exception:
                continue

        for sel in search_selectors:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=2000):
                    search_inp = loc
                    break
            except Exception:
                continue

    if search_inp is None:
        log("[ВНИМАНИЕ] Поле «Поиск по ПВЗ/постамату» не найдено!")
        return False

    # 3. Вводим запрос в поле поиска ПВЗ
    try:
        search_inp.scroll_into_view_if_needed(timeout=2000)
        search_inp.click()
        search_inp.press("ControlOrMeta+A")
        search_inp.press("Backspace")
        search_inp.type(query, delay=40)
    except Exception as e:
        log(f"[ВНИМАНИЕ] Ошибка ввода в поиск ПВЗ: {e}")
        return False

    page.wait_for_timeout(1800)

    # 4. Кликаем по найденному пункту в списке слева (по коду, короткому адресу или первому пункту «Пункт выдачи» / «Постамат»)
    candidates = [c for c in (code, short_addr, addr) if c]
    if short_addr:
        first_part = short_addr.split(",")[0].strip()
        if first_part and first_part not in candidates:
            candidates.append(first_part)

    picked = False
    for cand in candidates:
        try:
            # Ищем карточку в списке ПВЗ (ниже заголовка «Доставить в ПВЗ»)
            xp = f"xpath=//*[contains(normalize-space(.), 'Доставить в ПВЗ')][last()]/following::*[contains(translate(normalize-space(.), 'АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ', 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'), '{cand.lower()}') and not(self::input)][1]"
            loc = page.locator(xp).first
            if loc.is_visible(timeout=1800):
                loc.click(force=True, timeout=2500)
                picked = True
                break
        except Exception:
            continue

    # Резерв: кликаем по первому отфильтрованному пункту в списке слева
    if not picked:
        for fallback_text in ("Пункт выдачи", "Постамат"):
            try:
                xp = f"xpath=//*[contains(normalize-space(.), 'Доставить в ПВЗ')][last()]/following::*[normalize-space(.)='{fallback_text}'][1]"
                loc = page.locator(xp).first
                if loc.is_visible(timeout=1500):
                    loc.click(force=True, timeout=2500)
                    picked = True
                    break
            except Exception:
                continue

    page.wait_for_timeout(1000)

    # 5. Если появилась кнопка «ВЫБРАТЬ» — нажимаем её
    for btn_text in ("ВЫБРАТЬ", "Выбрать", "Выбрать пункт"):
        try:
            btn = page.get_by_role("button", name=btn_text, exact=False).last
            if btn.is_visible(timeout=1200):
                btn.click(force=True, timeout=2000)
                page.wait_for_timeout(700)
                break
        except Exception:
            pass

    if picked:
        log(f"-> ПВЗ выбран: {query}")
        return True

    log(f"[ВНИМАНИЕ] Не удалось выбрать ПВЗ «{query}».")
    return False


def _fill_order_comment(page: Page, comment: str, log: Callable[[str], None]) -> bool:
    """Надёжно заполняет textarea в блоке 'Комментарий к заказу' (например, 'УПД')."""
    text = (comment or "").strip()
    if not text:
        return False

    try:
        focused = page.evaluate(
            """() => {
                const all = Array.from(document.querySelectorAll('h1, h2, h3, h4, div, label, span'));
                const titleEl = all.find(el => {
                    if (el.children.length > 1) return false;
                    const t = (el.innerText || el.textContent || '').trim().toLowerCase();
                    return t === 'комментарий к заказу';
                });
                if (titleEl) {
                    let box = titleEl.parentElement;
                    for (let i = 0; i < 4 && box; i++) {
                        const ta = box.querySelector('textarea:not([disabled])');
                        if (ta && ta.offsetParent !== null) {
                            ta.scrollIntoView({block: 'center'});
                            ta.focus();
                            ta.click();
                            return true;
                        }
                        box = box.parentElement;
                    }
                }
                const tas = Array.from(document.querySelectorAll('textarea:not([disabled])')).filter(el => el.offsetParent !== null);
                if (tas.length > 0) {
                    const lastTa = tas[tas.length - 1];
                    lastTa.scrollIntoView({block: 'center'});
                    lastTa.focus();
                    lastTa.click();
                    return true;
                }
                return false;
            }"""
        )
        if focused:
            page.wait_for_timeout(200)
            page.keyboard.press("ControlOrMeta+A")
            page.keyboard.press("Backspace")
            page.keyboard.type(text, delay=35)
            page.keyboard.press("Tab")
            page.wait_for_timeout(400)
            log(f"-> Комментарий к заказу вписан: {text}")
            return True
    except Exception:
        pass

    try:
        ta = page.locator("textarea").last
        if _fill_locator(ta, text, press_tab=True):
            log(f"-> Комментарий к заказу вписан (textarea): {text}")
            return True
    except Exception:
        pass

    log("[ВНИМАНИЕ] Не удалось вписать комментарий к заказу!")
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
        xp = f"xpath={pref}/following::*[contains(normalize-space(.), '{button_text}') and not(descendant::*[contains(normalize-space(.), '{button_text}')])][1]"
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


def _dismiss_popups_once(page: Page, log: Callable[[str], None]) -> bool:
    """Одна быстрая попытка закрыть всплывающее окно 'ХОРОШО'."""
    pattern = re.compile(r"^\s*(хорошо|понятно|закрыть)\s*$", re.IGNORECASE)

    for frame in page.frames:
        try:
            btn = frame.get_by_role("button", name=pattern).first
            if btn.is_visible(timeout=250):
                log("-> Нажимаю «ХОРОШО» во всплывающем окне...")
                btn.click(force=True, timeout=2000)
                page.wait_for_timeout(500)
                return True
        except Exception:
            pass

        try:
            loc = frame.get_by_text(pattern).first
            if loc.is_visible(timeout=250):
                log("-> Нажимаю «ХОРОШО» во всплывающем окне...")
                loc.click(force=True, timeout=2000)
                page.wait_for_timeout(500)
                return True
        except Exception:
            pass

    try:
        clicked_js = page.evaluate(
            """() => {
                const targets = Array.from(document.querySelectorAll('button, a, div, span'));
                for (const el of targets) {
                    const txt = (el.innerText || el.textContent || '').trim().toLowerCase();
                    if (txt === 'хорошо' && el.offsetParent !== null) {
                        el.click();
                        return 'хорошо';
                    }
                }
                const modalText = (document.body && document.body.innerText) || '';
                if (modalText.toLowerCase().includes('войти по номеру телефона')) {
                    const closeBtn = document.querySelector('[class*="close" i], [aria-label*="close" i], [aria-label*="закрыть" i]');
                    if (closeBtn) {
                        closeBtn.click();
                        return 'close';
                    }
                }
                return null;
            }"""
        )
        if clicked_js:
            log(f"-> Закрыл всплывающее окно ({clicked_js})...")
            page.wait_for_timeout(500)
            return True
    except Exception:
        pass

    return False


def _dismiss_popups(page: Page, log: Callable[[str], None], wait_sec: float = 4.0) -> bool:
    deadline = time.time() + wait_sec
    while time.time() < deadline:
        if _dismiss_popups_once(page, log):
            return True
        page.wait_for_timeout(350)
    return False


def _wait_for_cabinet_loaded(page: Page, log: Callable[[str], None], timeout_sec: int = 180) -> bool:
    """Ждёт входа в личный кабинет по URL или содержимому и сразу закрывает модалку 'ХОРОШО'."""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        url = (page.url or "").lower()
        if "order-history" in url or (
            "lk.cdek.ru" in url
            and "login" not in url
            and "auth" not in url
            and url.rstrip("/") != "https://lk.cdek.ru"
        ):
            _dismiss_popups(page, log, wait_sec=3.5)
            return True

        if _dismiss_popups_once(page, log):
            return True

        try:
            has_menu = page.evaluate(
                """() => {
                    const t = (document.body && document.body.innerText) || '';
                    return t.includes('Список заказов') || t.includes('Новый заказ');
                }"""
            )
            if has_menu:
                _dismiss_popups(page, log, wait_sec=3.5)
                return True
        except Exception:
            pass

        page.wait_for_timeout(500)
    return False


def _fill_city_field(page: Page, field_label: str, city_value: str, use_moscow_quicklink: bool = False) -> bool:
    """Заполняет поле города отправителя или получателя и выбирает город из выпадающего списка."""
    if not city_value:
        return False

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
            if not _wait_for_cabinet_loaded(page, log, timeout_sec=180):
                raise RuntimeError("Не удалось дождаться входа в личный кабинет СДЭК.")

            # --- ШАГ 2: КЛИК «Новый заказ» / «НОВЫЙ ЗАКАЗ» ---
            log("3. Открываю «Новый заказ»...")
            opened_new_order = False
            for _ in range(4):
                _dismiss_popups_once(page, log)
                clicked = False
                for selector in (
                    "a:has-text('Новый заказ')",
                    "button:has-text('НОВЫЙ ЗАКАЗ')",
                    "text=Новый заказ",
                    "text=НОВЫЙ ЗАКАЗ",
                ):
                    try:
                        loc = page.locator(selector).first
                        if loc.is_visible(timeout=1500):
                            loc.click(force=True, timeout=3000)
                            clicked = True
                            break
                    except Exception:
                        continue

                if clicked:
                    try:
                        page.wait_for_selector("text=О заказе", timeout=8000)
                        opened_new_order = True
                        break
                    except Exception:
                        pass
                page.wait_for_timeout(800)

            if not opened_new_order:
                page.wait_for_selector("text=О заказе", timeout=25000)

            page.wait_for_timeout(1500)

            # --- ШАГ 3: БЛОК «О ЗАКАЗЕ» ---
            log("4. Заполняю блок «О заказе» (Отправитель: Москва -> Город получателя)...")
            _click_in_section(page, "О заказе", order.get("role", "ОТПРАВИТЕЛЕМ"))
            _click_in_section(page, "О заказе", order.get("payer", "ПО ДОГОВОРУ"))
            page.wait_for_timeout(400)

            _fill_city_field(page, "Город отправителя", "Москва", use_moscow_quicklink=True)

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
                _fill_after_label(page, "Наименование", order.get("recipient_fio", ""), section_title="Получатель")

            _fill_after_label(page, "ФИО", order.get("recipient_fio", ""), section_title="Получатель")
            _fill_phone_in_section(page, "Получатель", order.get("recipient_phone", ""))
            if order.get("recipient_email"):
                _fill_after_label(page, "Электронная почта", order["recipient_email"], section_title="Получатель")

            # --- ШАГ 6: БЛОК «ТОВАРЫ» (Вес, Длина, Ширина, Высота, Описание груза = ПЛАТЫ) ---
            log("7. Заполняю товары (вес, габариты, описание груза)...")
            _fill_after_label(page, "Вес", order.get("weight", "0.5"), section_title="Товары")
            _fill_after_label(page, "Длина", order.get("length", "10"), section_title="Товары")
            _fill_after_label(page, "Ширина", order.get("width", "10"), section_title="Товары")
            _fill_after_label(page, "Высота", order.get("height", "5"), section_title="Товары")
            _fill_cargo_description(page, order.get("description", "ПЛАТЫ"), log)

            # Опускаемся вниз и ждём, пока СДЭК раскроет блок «Тарифы»
            log("-> Опускаюсь вниз и жду загрузку тарифов...")
            page.evaluate("window.scrollBy(0, 500)")
            try:
                page.wait_for_selector("text=КУРЬЕР ЗАБЕРЁТ ПО АДРЕСУ", timeout=15000)
            except Exception:
                page.wait_for_timeout(2000)

            # --- ШАГ 7: БЛОК «ТАРИФЫ» ---
            log("8. Выбираю тариф (Курьер заберёт по адресу -> В ПВЗ -> Экспресс дверь-склад)...")
            _safe_click_text(page, order.get("pickup_from", "КУРЬЕР ЗАБЕРЁТ ПО АДРЕСУ"), timeout=4000)
            page.wait_for_timeout(400)
            _safe_click_text(page, order.get("delivery_to", "В ПВЗ"), timeout=4000)
            page.wait_for_timeout(2200)
            _safe_click_text(page, order.get("tariff", "Экспресс дверь-склад"), timeout=5000)
            page.wait_for_timeout(1200)

            # --- ШАГ 8: ДОПОЛНИТЕЛЬНЫЕ УСЛУГИ (ОБЪЯВЛЕННАЯ СТОИМОСТЬ 3000) ---
            if order.get("use_insurance") and order.get("declared_value"):
                log(f"9. Указываю объявленную стоимость ({order['declared_value']})...")
                _fill_declared_value(page, order["declared_value"], log)

            # --- ШАГ 9: ИНФОРМАЦИЯ ОБ ОТПРАВЛЕНИИ (ЗАБОР КУРЬЕРОМ: АДРЕС, ДАТА, ВРЕМЯ) ---
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
                press_tab=True,
            )
            page.wait_for_timeout(500)
            _select_pickup_time(page, order.get("time_from", "12:00"), order.get("time_to", "15:00"), log)

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
                _select_pvz_on_cdek(page, order.get("pvz_code", ""), order.get("pvz_address", ""), log)
            elif delivery_to == "КУРЬЕРОМ ПО АДРЕСУ" and order.get("pvz_address"):
                log(f"11. Заполняю адрес доставки курьером: {order['pvz_address']}...")
                _fill_after_label(page, "Улица", order["pvz_address"], section_title="Информация об отправлении")

            # --- ШАГ 11: КОММЕНТАРИЙ К ЗАКАЗУ (УПД) ---
            log("12. Заполняю комментарий к заказу...")
            if order.get("order_comment"):
                _fill_order_comment(page, order["order_comment"], log)

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
