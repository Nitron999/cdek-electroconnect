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
    """
    Если забор сегодня и текущее время уже дошло до начала слота или прошло его —
    сдвигает старт вверх с шагом 30 минут и сохраняет длительность (минимум 3 часа).
    """
    now = datetime.datetime.now()
    today = now.date()

    try:
        target_date = datetime.datetime.strptime((date_str or "").strip(), "%d.%m.%Y").date()
    except Exception:
        target_date = today

    def _to_min(val: str, default_m: int) -> int:
        try:
            h, m = map(int, (val or "").strip().split(":"))
            if 0 <= h <= 23 and 0 <= m <= 59:
                return h * 60 + m
        except Exception:
            pass
        return default_m

    def _fmt(m: int) -> str:
        return f"{m // 60:02d}:{m % 60:02d}"

    start_m = _to_min(time_from, 12 * 60)
    end_m = _to_min(time_to, 15 * 60)
    duration = max(180, end_m - start_m)

    if target_date <= today:
        target_date = today
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


def _select_tariff_door_to_pvz(page: Page, tariff_name: str, log: Callable[[str], None]) -> None:
    """Жёстко выбирает: Откуда = КУРЬЕР ЗАБЕРЁТ ПО АДРЕСУ, Куда = В ПВЗ, и проверяет переход на дверь-склад."""
    log("8. Выбираю тариф: КУРЬЕР ЗАБЕРЁТ ПО АДРЕСУ -> В ПВЗ...")

    def _click_by_regex(pattern_str: str) -> bool:
        rx = re.compile(pattern_str, re.IGNORECASE)
        try:
            loc = page.get_by_text(rx).first
            loc.scroll_into_view_if_needed(timeout=2000)
            if loc.is_visible(timeout=2000):
                loc.click(force=True, timeout=3000)
                return True
        except Exception:
            pass

        try:
            return bool(
                page.evaluate(
                    """(pat) => {
                        const re = new RegExp(pat, 'i');
                        const els = Array.from(document.querySelectorAll('button, [role="tab"], [role="radio"], label, div, span'));
                        for (const el of els) {
                            if (el.offsetParent === null || el.children.length > 2) continue;
                            const txt = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
                            if (re.test(txt)) {
                                el.scrollIntoView({block: 'center'});
                                el.click();
                                return true;
                            }
                        }
                        return false;
                    }""",
                    pattern_str,
                )
            )
        except Exception:
            return False

    switched = False
    for attempt in range(3):
        _click_by_regex(r"^\s*курьер\s+забер[её]т\s+по\s+адресу\s*$")
        page.wait_for_timeout(500)
        _click_by_regex(r"^\s*в\s+пвз\s*$")
        page.wait_for_timeout(1500)

        try:
            has_door_sklad = page.evaluate(
                """() => ((document.body && document.body.innerText) || '').toLowerCase().includes('дверь-склад')"""
            )
            if has_door_sklad:
                switched = True
                log("-> Режим «Курьер заберёт по адресу -> В ПВЗ» подтверждён (дверь-склад).")
                break
        except Exception:
            pass
        log(f"-> Повторно переключаю «Курьер заберёт по адресу -> В ПВЗ» (попытка {attempt + 2})...")

    if not switched:
        log("[ВНИМАНИЕ] Не удалось подтвердить переключение на «дверь-склад».")

    target_tariff = (tariff_name or "Экспресс дверь-склад").strip()
    if not _safe_click_text(page, target_tariff, timeout=4000):
        _safe_click_text(page, "Экспресс дверь-склад", timeout=4000)
    page.wait_for_timeout(1200)


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
    """
    Находит два поля времени забора напрямую по их реальным селекторам СДЭК:
    input[data-testid*="senderCourierTimepickersArrivalTime"] / input.uikit-input-control[placeholder="--:--"],
    открывает выпадающую сетку кликом по цифрам (мимо крестика) и выбирает нужное время.
    """
    if not time_from and not time_to:
        return

    try:
        page.keyboard.press("Escape")
    except Exception:
        pass
    page.wait_for_timeout(800)

    def _to_min(t_str: str) -> int:
        try:
            h, m = map(int, t_str.strip().split(":"))
            return h * 60 + m
        except Exception:
            return -1

    def _fmt_min(m: int) -> str:
        return f"{m // 60:02d}:{m % 60:02d}"

    def _find_two_time_inputs():
        selectors = [
            "input[data-testid*='senderCourierTimepickersArrivalTime']",
            "input[data-testid*='senderCourierTimepickers'][placeholder='--:--']",
            "input.uikit-input-control[placeholder='--:--']",
        ]
        for sel in selectors:
            loc = page.locator(sel)
            cnt = loc.count()
            vis = []
            for i in range(cnt):
                el = loc.nth(i)
                try:
                    if el.is_visible(timeout=300):
                        vis.append(el)
                        if len(vis) == 2:
                            return vis
                except Exception:
                    continue
        return []

    def _read_val(inp) -> str:
        try:
            return (inp.input_value() or "").strip()
        except Exception:
            return ""

    def _read_popup_options(inp_box: dict) -> list[dict]:
        """Считывает все доступные ячейки времени ЧЧ:ММ из открывшейся сетки (сверху или снизу от поля)."""
        try:
            return page.evaluate(
                """({cx, cy}) => {
                    const isVis = (el) => {
                        const s = window.getComputedStyle(el);
                        if (s.display === 'none' || s.visibility === 'hidden' || parseFloat(s.opacity) === 0) return false;
                        if (s.pointerEvents === 'none') return false;
                        const r = el.getBoundingClientRect();
                        return r.width >= 15 && r.height >= 12;
                    };
                    const all = Array.from(document.querySelectorAll('div, span, li, button, td, a, p'));
                    const opts = [];
                    for (const el of all) {
                        if (el.tagName === 'INPUT' || !isVis(el)) continue;
                        const txt = (el.innerText || el.textContent || '').trim();
                        if (!/^\\d{2}:\\d{2}$/.test(txt)) continue;
                        const hasChild = Array.from(el.children).some(
                            c => (c.innerText || c.textContent || '').trim() === txt
                        );
                        if (hasChild) continue;
                        const cls = (el.className || '').toString().toLowerCase();
                        if (el.disabled || cls.includes('disabled') || cls.includes('inactive')) continue;
                        const r = el.getBoundingClientRect();
                        const ox = r.left + r.width / 2;
                        const oy = r.top + r.height / 2;
                        // Ячейки сетки всегда рядом с полем (до 450px по вертикали/горизонтали)
                        if (Math.abs(ox - cx) > 450 || Math.abs(oy - cy) > 450) continue;
                        opts.push({val: txt, x: ox, y: oy});
                    }
                    const byVal = new Map();
                    for (const o of opts) byVal.set(o.val, o);
                    return Array.from(byVal.values());
                }""",
                {"cx": inp_box["x"] + inp_box["width"] / 2, "cy": inp_box["y"] + inp_box["height"] / 2},
            ) or []
        except Exception:
            return []

    def _open_and_pick(inp, desired_time: str) -> str | None:
        if not desired_time:
            return desired_time
        if _read_val(inp) == desired_time:
            return desired_time

        try:
            inp.evaluate("el => el.scrollIntoView({block: 'center'})")
            page.wait_for_timeout(200)
            box = inp.bounding_box()
        except Exception:
            return None

        if not box:
            return None

        # 1. Кликаем по левой части поля (прямо по цифрам, мимо серого крестика)
        inp.click(position={"x": min(22, box["width"] * 0.25), "y": box["height"] / 2}, timeout=2500)
        page.wait_for_timeout(550)
        opts = _read_popup_options(box)

        # 2. Если сетка не открылась — кликаем по зелёной кнопке с часами справа от input
        if len(opts) < 2:
            page.mouse.click(box["x"] + box["width"] + 16, box["y"] + box["height"] / 2)
            page.wait_for_timeout(550)
            opts = _read_popup_options(box)

        if opts:
            desired_m = _to_min(desired_time)
            chosen = next((o for o in opts if o["val"] == desired_time), None)
            if chosen is None and desired_m >= 0:
                opts_sorted = sorted(opts, key=lambda o: _to_min(o["val"]))
                chosen = next((o for o in opts_sorted if _to_min(o["val"]) >= desired_m), opts_sorted[-1])
                log(
                    f"-> В сетке нет {desired_time} (доступно: {opts_sorted[0]['val']}..{opts_sorted[-1]['val']}), "
                    f"выбираю {chosen['val']}"
                )

            if chosen:
                page.mouse.click(chosen["x"], chosen["y"])
                page.wait_for_timeout(500)
                if _read_val(inp) == chosen["val"]:
                    return chosen["val"]

        # 3. Резерв: прямой ввод в masked-input (если сетка не перехватила клик)
        try:
            inp.click(position={"x": min(22, box["width"] * 0.25), "y": box["height"] / 2}, timeout=2000)
            page.wait_for_timeout(150)
            page.keyboard.press("ControlOrMeta+A")
            page.keyboard.press("Backspace")
            page.keyboard.type(desired_time.replace(":", ""), delay=45)
            page.keyboard.press("Enter")
            page.wait_for_timeout(400)
            if _read_val(inp) == desired_time:
                return desired_time
        except Exception:
            pass

        return None

    for attempt in range(3):
        inps = _find_two_time_inputs()
        if len(inps) < 2:
            log(f"-> Попытка {attempt + 1}: поля времени (uikit-input-control) не найдены, жду...")
            page.wait_for_timeout(800)
            continue

        inp_from, inp_to = inps[0], inps[1]
        cur_from = _read_val(inp_from)
        cur_to = _read_val(inp_to)
        if attempt == 0:
            log(f"-> Найдены поля времени СДЭК: {cur_from or '?'} - {cur_to or '?'}")

        if cur_from == time_from and cur_to == time_to:
            log(f"-> Время забора подтверждено: {cur_from} - {cur_to}")
            return

        # Если нужно сдвинуть конец вперёд — сначала правое поле, затем левое
        if _to_min(time_to) > _to_min(cur_to) >= 0:
            _open_and_pick(inp_to, time_to)
            page.wait_for_timeout(350)
            _open_and_pick(inp_from, time_from)
        else:
            picked_from = _open_and_pick(inp_from, time_from)
            page.wait_for_timeout(350)
            if picked_from and _to_min(picked_from) > _to_min(time_from):
                time_from = picked_from
                time_to = _fmt_min(_to_min(picked_from) + 180)
            _open_and_pick(inp_to, time_to)

        v1 = _read_val(inp_from)
        v2 = _read_val(inp_to)
        if v1 == time_from and v2 == time_to:
            log(f"-> Время забора установлено и подтверждено: {v1} - {v2}")
            return

        log(f"-> Попытка {attempt + 1}: сейчас в полях {v1 or '?'} - {v2 or '?'}, нужно {time_from} - {time_to}...")
        page.keyboard.press("Escape")
        page.wait_for_timeout(450)

    inps_end = _find_two_time_inputs()
    v1 = _read_val(inps_end[0]) if len(inps_end) > 0 else "?"
    v2 = _read_val(inps_end[1]) if len(inps_end) > 1 else "?"
    log(f"[ВНИМАНИЕ] Итоговое время в СДЭК: {v1} - {v2} (ожидалось {time_from} - {time_to})")


def _select_pvz_on_cdek(page: Page, pvz_code: str, pvz_address: str, log: Callable[[str], None]) -> bool:
    """Открывает поиск ПВЗ (или использует уже открытое поле), вводит адрес/код и выбирает пункт."""
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

    log(f"11. Выбираю ПВЗ: {query}...")

    search_selectors = [
        "input[placeholder*='Поиск по ПВЗ' i]",
        "input[placeholder*='постамат' i]",
        "input[placeholder*='пункт' i]",
        "input[placeholder*='Поиск' i]",
        "input[placeholder*='адрес' i]",
        "input[placeholder*='улиц' i]",
        "[role='dialog'] input[type='text']",
        ".modal input[type='text']",
    ]

    def _find_visible_search_input():
        for sel in search_selectors:
            try:
                inp = page.locator(sel).last
                if inp.is_visible(timeout=500):
                    return inp
            except Exception:
                continue
        return None

    pvz_inp = _find_visible_search_input()
    if pvz_inp is None:
        for sel in (
            "xpath=//*[contains(normalize-space(.), 'Доставить в ПВЗ')][last()]/following::*[normalize-space(.)='ИЗМЕНИТЬ' or normalize-space(.)='Изменить' or normalize-space(.)='ВЫБРАТЬ ПВЗ' or normalize-space(.)='Выбрать'][1]",
            "button:has-text('ИЗМЕНИТЬ')",
            "text=ИЗМЕНИТЬ",
        ):
            try:
                btn = page.locator(sel).first
                btn.scroll_into_view_if_needed(timeout=2000)
                if btn.is_visible(timeout=1500):
                    btn.click(force=True, timeout=3000)
                    page.wait_for_timeout(1500)
                    break
            except Exception:
                continue
        pvz_inp = _find_visible_search_input()

    if pvz_inp is None:
        log("[ВНИМАНИЕ] Поле поиска ПВЗ в СДЭК не найдено.")
        return False

    try:
        pvz_inp.scroll_into_view_if_needed(timeout=2000)
        pvz_inp.click()
        pvz_inp.press("ControlOrMeta+A")
        pvz_inp.press("Backspace")
        pvz_inp.type(query, delay=40)
    except Exception as e:
        log(f"[ВНИМАНИЕ] Ошибка ввода в поиск ПВЗ: {e}")
        return False

    page.wait_for_timeout(1800)

    candidates = [c for c in (code, addr, short_addr) if c]
    if short_addr:
        first_part = short_addr.split(",")[0].strip()
        if first_part and first_part not in candidates:
            candidates.append(first_part)

    picked_item = False
    for cand in candidates:
        try:
            clicked = page.evaluate(
                """(needle) => {
                    const low = needle.toLowerCase();
                    const els = Array.from(document.querySelectorAll('li, [role="option"], [class*="pvz" i], [class*="office" i], [class*="item" i], [class*="point" i], div, span'));
                    for (let i = els.length - 1; i >= 0; i--) {
                        const el = els[i];
                        if (el.offsetParent === null || el.tagName === 'INPUT') continue;
                        if (el.children.length > 3) continue;
                        const txt = (el.innerText || el.textContent || '').trim().toLowerCase();
                        if (txt.includes(low) && txt.length < 180) {
                            el.scrollIntoView({block: 'center'});
                            el.click();
                            return true;
                        }
                    }
                    return false;
                }""",
                cand,
            )
            if clicked:
                picked_item = True
                break
        except Exception:
            continue

    page.wait_for_timeout(1000)

    for btn_text in ("ВЫБРАТЬ", "Выбрать", "Выбрать пункт"):
        try:
            btn = page.get_by_role("button", name=btn_text, exact=False).last
            if btn.is_visible(timeout=1200):
                btn.click(force=True, timeout=2500)
                page.wait_for_timeout(800)
                log(f"-> ПВЗ выбран: {query}")
                return True
        except Exception:
            pass

    if picked_item:
        log(f"-> ПВЗ выбран из списка: {query}")
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


def _download_waybill_from_order_list(page: Page, context, copies: int, log: Callable[[str], None]) -> str | None:
    """
    Переходит в Список заказов -> три точки у самого верхнего заказа ->
    Распечатать документы -> Накладная (3 копии) -> РАСПЕЧАТАТЬ ->
    перехватывает PDF из открывшейся вкладки и сохраняет на диск для SumatraPDF.
    """
    log("14. Перехожу в «Список заказов» для печати накладной (3 копии)...")
    try:
        page.goto("https://lk.cdek.ru/order-history", wait_until="domcontentloaded", timeout=30000)
    except Exception:
        _safe_click_text(page, "Список заказов", timeout=4000)

    page.wait_for_timeout(2500)
    _dismiss_popups_once(page, log)

    try:
        page.wait_for_selector("text=Создан", timeout=15000)
    except Exception:
        pass
    page.wait_for_timeout(1200)

    log("-> Нажимаю три точки у последнего созданного заказа...")
    clicked_dots = False
    try:
        clicked_dots = bool(
            page.evaluate(
                """() => {
                    const rows = Array.from(document.querySelectorAll('tbody tr, [class*="order-row" i], [class*="table-row" i]'))
                        .filter(r => r.offsetParent !== null && /\\d{8,}/.test(r.innerText || ''));
                    if (rows.length > 0) {
                        const row = rows[0];
                        const btns = Array.from(row.querySelectorAll('button, [role="button"], svg, [class*="menu" i], [class*="more" i], [class*="dots" i]'))
                            .filter(el => el.offsetParent !== null);
                        if (btns.length > 0) {
                            let rightmost = btns[0];
                            let maxRight = rightmost.getBoundingClientRect().right;
                            for (const b of btns) {
                                const r = b.getBoundingClientRect().right;
                                if (r >= maxRight) {
                                    maxRight = r;
                                    rightmost = b;
                                }
                            }
                            rightmost.scrollIntoView({block: 'center'});
                            rightmost.click();
                            return true;
                        }
                    }
                    return false;
                }"""
            )
        )
    except Exception:
        clicked_dots = False

    if not clicked_dots:
        log("[ВНИМАНИЕ] Не удалось автоматически нажать три точки у заказа.")
        return None

    page.wait_for_timeout(800)

    log("-> Выбираю «Распечатать документы»...")
    if not _safe_click_text(page, "Распечатать документы", timeout=4000):
        log("[ВНИМАНИЕ] Пункт «Распечатать документы» не найден.")
        return None

    page.wait_for_timeout(1200)

    log(f"-> Выставляю «Накладная» — количество копий: {copies}...")
    _safe_click_text(page, "Накладная", timeout=2000)
    page.wait_for_timeout(300)

    if not _fill_after_label(page, "Количество копий", str(copies), press_tab=True):
        try:
            inp = page.locator("input[type='number'], [role='dialog'] input, .modal input").first
            _fill_locator(inp, str(copies), press_tab=True)
        except Exception:
            pass

    page.wait_for_timeout(400)

    log("-> Нажимаю «РАСПЕЧАТАТЬ» и перехватываю PDF...")
    pdf_url = None
    new_page = None
    try:
        with context.expect_page(timeout=25000) as new_page_info:
            if not _safe_click_text(page, "РАСПЕЧАТАТЬ", timeout=4000, exact=True):
                _safe_click_text(page, "Распечатать", timeout=4000)
        new_page = new_page_info.value
        new_page.wait_for_load_state("domcontentloaded", timeout=20000)
        page.wait_for_timeout(1000)
        pdf_url = new_page.url
    except Exception as e:
        log(f"[ВНИМАНИЕ] Новая вкладка с PDF не открылась: {e}")
        return None

    if not pdf_url:
        return None

    try:
        resp = context.request.get(pdf_url, timeout=30000)
        if resp.ok:
            body = resp.body()
            filename = f"cdek_waybill_{int(time.time())}.pdf"
            pdf_path = os.path.join(DOWNLOADS_DIR, filename)
            with open(pdf_path, "wb") as f:
                f.write(body)
            log(f"-> PDF накладной ({copies} коп.) сохранён: {filename}")
            try:
                if new_page:
                    new_page.close()
            except Exception:
                pass
            return pdf_path
        else:
            log(f"[ВНИМАНИЕ] Не удалось скачать PDF (код {resp.status}).")
    except Exception as e:
        log(f"[ВНИМАНИЕ] Ошибка скачивания PDF: {e}")

    return None


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
            _dismiss_popups_once(page, log)
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
                _dismiss_popups_once(page, log)
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
    """Создаёт новый заказ в lk.cdek.ru, заполняет все поля и печатает 3 копии накладной через SumatraPDF."""
    login = order.get("login", "").strip()
    password = order.get("password", "").strip()

    pickup_date, time_from, time_to = _resolve_pickup_slot(
        order.get("pickup_date", ""),
        order.get("time_from", "12:00"),
        order.get("time_to", "15:00"),
        log,
    )

    with sync_playwright() as p:
        log("1. Запускаю браузер (геолокация отключена)...")
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--no-sandbox",
            "--deny-permission-prompts",
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
            permissions=[],
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
            # --- ШАГ 1: ВХОД ---
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

            # --- ШАГ 2: КЛИК «Новый заказ» ---
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

            # --- ШАГ 4: БЛОК «ОТПРАВИТЕЛЬ» ---
            log("5. Заполняю контактное лицо отправителя (Крылова)...")
            _fill_after_label(page, "ФИО", order.get("sender_fio", "Крылова Людмила Борисовна"), section_title="Отправитель")
            _fill_phone_in_section(page, "Отправитель", order.get("sender_phone", "+7 916 195 36 94"))

            # --- ШАГ 5: БЛОК «ПОЛУЧАТЕЛЬ» ---
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

            # --- ШАГ 6: БЛОК «ТОВАРЫ» ---
            log("7. Заполняю товары (вес, габариты, описание груза)...")
            _fill_after_label(page, "Вес", order.get("weight", "0.5"), section_title="Товары")
            _fill_after_label(page, "Длина", order.get("length", "10"), section_title="Товары")
            _fill_after_label(page, "Ширина", order.get("width", "10"), section_title="Товары")
            _fill_after_label(page, "Высота", order.get("height", "5"), section_title="Товары")
            _fill_cargo_description(page, order.get("description", "ПЛАТЫ"), log)

            log("-> Опускаюсь вниз и жду загрузку тарифов...")
            page.evaluate("window.scrollBy(0, 500)")
            try:
                page.wait_for_selector("text=Тарифы", timeout=15000)
            except Exception:
                page.wait_for_timeout(2000)

            # --- ШАГ 7: БЛОК «ТАРИФЫ» (ЖЁСТКО: КУРЬЕР ЗАБЕРЁТ ПО АДРЕСУ -> В ПВЗ) ---
            _select_tariff_door_to_pvz(page, order.get("tariff", "Экспресс дверь-склад"), log)

            # --- ШАГ 8: ДОПОЛНИТЕЛЬНЫЕ УСЛУГИ ---
            if order.get("use_insurance") and order.get("declared_value"):
                log(f"9. Указываю объявленную стоимость ({order['declared_value']})...")
                _fill_declared_value(page, order["declared_value"], log)

            # --- ШАГ 9: ИНФОРМАЦИЯ ОБ ОТПРАВЛЕНИИ ---
            log(f"10. Заполняю адрес, дату ({pickup_date}) и время забора ({time_from}-{time_to})...")
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
                pickup_date,
                section_title="Информация об отправлении",
                press_tab=True,
            )
            _select_pickup_time(page, time_from, time_to, log)

            if order.get("need_attorney"):
                _click_in_section(page, "Информация об отправлении", "Курьеру необходима доверенность", timeout=1500)
            if order.get("need_id_doc"):
                _click_in_section(
                    page,
                    "Информация об отправлении",
                    "Курьеру необходим документ удостоверяющий личность",
                    timeout=1500,
                )

            # --- ШАГ 10: ВЫБОР ПВЗ ---
            pvz_query = (order.get("pvz_code") or order.get("pvz_address") or "").strip()
            if pvz_query:
                _select_pvz_on_cdek(page, order.get("pvz_code", ""), order.get("pvz_address", ""), log)

            # --- ШАГ 11: КОММЕНТАРИЙ К ЗАКАЗУ (УПД) ---
            log("12. Заполняю комментарий к заказу...")
            if order.get("order_comment"):
                _fill_order_comment(page, order["order_comment"], log)

            # --- ШАГ 12: СОЗДАНИЕ ЗАКАЗА ---
            log("13. Нажимаю «СОЗДАТЬ ЗАКАЗ»...")
            _safe_click_text(page, "СОЗДАТЬ ЗАКАЗ", timeout=5000)
            page.wait_for_timeout(5000)

            # --- ШАГ 13: СПИСОК ЗАКАЗОВ -> ТРИ ТОЧКИ -> РАСПЕЧАТАТЬ ДОКУМЕНТЫ (3 КОПИИ) -> SUMATRAPDF ---
            pdf_path = _download_waybill_from_order_list(page, context, copies=3, log=log)

            if pdf_path:
                ok, msg = print_pdf_silent(pdf_path)
                log(f"-> {msg}")
                add_history_entry(
                    {
                        "recipient": order.get("recipient_fio", ""),
                        "city_to": order.get("city_to", ""),
                        "date": pickup_date,
                        "tariff": order.get("tariff", ""),
                        "pvz": pvz_query,
                        "pdf": os.path.basename(pdf_path),
                        "printed": ok,
                    }
                )

            log("ГОТОВО! Заказ оформлен и отправлен на печать.")
            page.wait_for_timeout(3000)
        finally:
            browser.close()
