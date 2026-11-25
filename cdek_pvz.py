import requests
from playwright.sync_api import sync_playwright


def _extract_city_name(city_full: str) -> str:
    """Из 'Ижевск, Удмуртия, Россия' оставляет 'Ижевск'."""
    return (city_full or "").split(",")[0].strip()


def _parse_pvz_list(raw_items: list) -> list[dict]:
    result = []
    seen = set()
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or item.get("Code") or "").strip()
        loc = item.get("location") or {}
        address = (
            loc.get("address")
            or item.get("address")
            or item.get("Address")
            or item.get("fullAddress")
            or ""
        ).strip()
        if not address and not code:
            continue
        key = code or address
        if key in seen:
            continue
        seen.add(key)

        raw_type = str(item.get("type") or item.get("Type") or "PVZ").upper()
        pvz_type = "Постамат" if "POSTAMAT" in raw_type or "ПОСТАМАТ" in raw_type else "Пункт выдачи"
        work_time = str(item.get("work_time") or item.get("workTime") or item.get("WorkTime") or "").strip()
        result.append(
            {
                "code": code,
                "type": pvz_type,
                "address": address,
                "work_time": work_time,
            }
        )
    return result


def fetch_cdek_pvz(city_full: str) -> tuple[list[dict], str]:
    """Загружает пункты выдачи и постаматы СДЭК для указанного города."""
    city = _extract_city_name(city_full)
    if not city:
        return [], "Укажи город получателя."

    # 1. Быстрая попытка через публичный эндпоинт СДЭК
    try:
        resp = requests.get(
            "https://integration.cdek.ru/pvzlist/v1/json",
            params={"cityName": city, "type": "ALL"},
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if resp.status_code == 200:
            data = resp.json()
            raw = data.get("pvz") if isinstance(data, dict) else data
            if isinstance(raw, list) and raw:
                parsed = _parse_pvz_list(raw)
                if parsed:
                    return parsed, f"Загружено {len(parsed)} пунктов ({city})"
    except Exception:
        pass

    # 2. Резервный способ: подтягиваем список ПВЗ с сайта cdek.ru в фоне
    collected = []
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(channel="chrome", headless=True)
            except Exception:
                browser = p.chromium.launch(headless=True)

            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
            )

            def handle_response(response):
                try:
                    url = response.url.lower()
                    if any(k in url for k in ("office", "pvz", "deliverypoint")):
                        ct = response.headers.get("content-type", "")
                        if "json" in ct:
                            body = response.json()
                            if isinstance(body, list):
                                collected.extend(_parse_pvz_list(body))
                            elif isinstance(body, dict):
                                for k in ("data", "items", "pvz", "offices", "deliverypoints"):
                                    if isinstance(body.get(k), list):
                                        collected.extend(_parse_pvz_list(body[k]))
                except Exception:
                    pass

            page.on("response", handle_response)
            page.goto("https://www.cdek.ru/ru/offices", wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(2000)

            search_inp = page.locator("input[placeholder*='город' i], input[placeholder*='адрес' i]").first
            if search_inp.is_visible(timeout=3000):
                search_inp.click()
                search_inp.fill(city)
                page.wait_for_timeout(1500)
                page.keyboard.press("ArrowDown")
                page.keyboard.press("Enter")
                page.wait_for_timeout(3000)

            browser.close()
    except Exception as e:
        return [], f"Не удалось подгрузить ПВЗ автоматически ({e}). Можно ввести адрес/код ПВЗ вручную."

    if collected:
        # Убираем дубликаты
        unique = {}
        for item in collected:
            unique[item["code"] or item["address"]] = item
        items = list(unique.values())
        return items, f"Загружено {len(items)} пунктов ({city})"

    return [], f"ПВЗ для «{city}» не найдены автоматически — впиши код (напр. IZHV16) или адрес вручную."
