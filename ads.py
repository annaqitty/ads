"""
Multi-source free ad scraper with traffic + commission metrics.
Keyword matches the output filename exactly. Try-all: one source failing
never stops the run.
"""

import os
import re
import csv
import time
import random
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------
KEYWORD = os.getenv("KEYWORD", "shopee")   # filename = this exact string
COUNTRY = os.getenv("COUNTRY", "ID")
TARGET  = int(os.getenv("TARGET", "500"))
OUT_DIR = "output"
IDN     = ZoneInfo("Asia/Jakarta")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

os.makedirs(OUT_DIR, exist_ok=True)

# filename label == keyword, sanitized but CASE-PRESERVED
def file_label(kw: str) -> str:
    return re.sub(r"[\s_]+", "-", re.sub(r"[^\w\s-]", "", kw).strip()) or "keyword"

LABEL = file_label(KEYWORD)

# every row carries these; sources fill what they can
SCHEMA = ["keyword", "advertiser", "ad_text", "started", "platform",
          "status", "traffic", "commission_rate", "cpc", "ctr",
          "impressions", "link"]


# ----------------------------------------------------------------------
# HELPERS
# ----------------------------------------------------------------------
def stamp():
    now = datetime.now(IDN)
    return now.strftime("%Y-%m-%d"), now.strftime("%H-%M-%S")


def build_name(kind):
    d, t = stamp()
    return os.path.join(OUT_DIR, f"{LABEL}-{kind}_({d}_{t}).txt")


def row(**kw):
    """Build a row padded to SCHEMA; missing metrics stay blank."""
    base = {k: "" for k in SCHEMA}
    base["keyword"] = KEYWORD
    base.update({k: v for k, v in kw.items() if k in SCHEMA})
    return base


def save_rows(rows, kind):
    path = build_name(kind)
    if not rows:
        print(f"[!] {kind}: 0 rows -> {path}")
        return path
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=SCHEMA)
        w.writeheader()
        w.writerows(rows)
    print(f"[+] {kind}: saved {len(rows)} rows -> {path}")
    return path


def clean(t):
    return " ".join((t or "").split()).strip()


def num(t):
    """Strip %, $, commas -> float-ish string; keep blank if absent."""
    if t is None:
        return ""
    s = re.sub(r"[^\d.]", "", str(t))
    return s


def safe(fn):
    name = fn.__name__.replace("src_", "")
    try:
        print(f"[>] trying source: {name}")
        rows = fn() or []
        print(f"    {name}: {len(rows)} rows")
        return name, rows
    except Exception as e:
        print(f"    {name}: FAILED -> {type(e).__name__}: {e}")
        traceback.print_exc(limit=1)
        return name, []


# ----------------------------------------------------------------------
# SOURCE 1 - META AD LIBRARY (traffic via link, no commission)
# ----------------------------------------------------------------------
def src_meta_ad_library():
    rows = []
    url = "https://www.facebook.com/ads/library/async/search_ads/"
    params = {
        "q": KEYWORD, "count": 30, "active_status": "active",
        "ad_type": "all", "country": COUNTRY, "media_type": "all",
        "search_type": "keyword_unordered",
    }
    h = {"user-agent": UA, "x-requested-with": "XMLHttpRequest"}
    cursor = None
    for _ in range(25):
        p = dict(params)
        if cursor:
            p["cursor"] = cursor
        r = requests.get(url, params=p, headers=h, timeout=30)
        data = r.json()
        results = data.get("results") or data.get("ads") or []
        for a in results:
            snap = a.get("snapshot", {}) or {}
            body = snap.get("body")
            text = body.get("text", "") if isinstance(body, dict) else (body or "")
            ad_id = a.get("ad_archive_id") or a.get("id", "")
            rows.append(row(
                advertiser=snap.get("page_name") or a.get("page_name", ""),
                ad_text=clean(text),
                started=a.get("start_date", ""),
                platform="meta", status="active",
                link=f"https://www.facebook.com/ads/library/?id={ad_id}" if ad_id else "",
            ))
        cursor = data.get("cursor")
        if not cursor or not results:
            break
        time.sleep(random.uniform(0.8, 1.5))
    return rows[:TARGET]


# ----------------------------------------------------------------------
# SOURCE 2 - TIKTOK CREATIVE CENTER (impressions, ctr, traffic)
# ----------------------------------------------------------------------
def src_tiktok_creative_center():
    rows = []
    url = "https://ads.tiktok.com/creative_radar_api/v1/top_ads/v2/list"
    params = {"period": 30, "page": 1, "limit": 20,
              "order_by": "ctr", "country_code": COUNTRY}
    h = {"user-agent": UA}
    for page in range(1, 26):
        params["page"] = page
        r = requests.get(url, params=params, headers=h, timeout=30)
        js = r.json()
        items = (js.get("data") or {}).get("list") or []
        if not items:
            break
        for it in items:
            rows.append(row(
                advertiser=it.get("brand_name", ""),
                ad_text=clean(it.get("ad_title", "")),
                started=str(it.get("first_shown_date", "")),
                platform="tiktok", status="active",
                impressions=num(it.get("impressions")),
                ctr=num(it.get("ctr")),
                traffic=num(it.get("reach") or it.get("impressions")),
                link=it.get("detail_url") or it.get("landing_page", ""),
            ))
        time.sleep(random.uniform(0.6, 1.2))
    return rows[:TARGET]


# ----------------------------------------------------------------------
# SOURCE 3 - GOOGLE ADS TRANSPARENCY (link)
# ----------------------------------------------------------------------
def src_google_transparency():
    rows = []
    url = f"https://adstransparency.google.com/?region={COUNTRY}&query={KEYWORD}"
    r = requests.get(url, headers={"user-agent": UA}, timeout=30)
    soup = BeautifulSoup(r.text, "html.parser")
    for card in soup.select("a[href*='advertiser']")[:TARGET]:
        href = card.get("href", "")
        rows.append(row(
            advertiser=clean(card.get_text()),
            platform="google", status="active",
            link=("https://adstransparency.google.com" + href) if href.startswith("/") else href,
        ))
    return rows


# ----------------------------------------------------------------------
# BROWSER SOURCES (BigSpy / Dropispy / IXSPY) - commission + traffic
# ----------------------------------------------------------------------
def _browser_scrape(page, url, row_sel, cell_map, platform, link_attr="a[href]"):
    page.goto(url, wait_until="domcontentloaded")
    time.sleep(4)
    page.wait_for_selector(row_sel, timeout=30000)
    rows = []
    for tr in page.query_selector_all(row_sel)[:TARGET]:
        cells = tr.query_selector_all("td, .cell, div[class*='col']")
        vals = [clean(c.inner_text()) for c in cells]
        rec = {"platform": platform, "status": "active"}
        for key, idx in cell_map.items():
            rec[key] = vals[idx] if idx < len(vals) else ""
        a = tr.query_selector(link_attr)
        rec["link"] = a.get_attribute("href") if a else ""
        if any(rec.get(k) for k in cell_map):
            rows.append(row(**rec))
    return rows


def src_bigspy():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        pg = b.new_page(user_agent=UA)
        try:
            return _browser_scrape(
                pg, f"https://bigspy.com/search?keyword={KEYWORD}",
                "table tbody tr, div[class*='ad-item']",
                {"advertiser": 0, "ad_text": 1, "started": 2,
                 "traffic": 3, "commission_rate": 4}, "bigspy")
        finally:
            b.close()


def src_dropispy():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        pg = b.new_page(user_agent=UA)
        try:
            return _browser_scrape(
                pg, f"https://dropispy.com/search?q={KEYWORD}",
                "div[class*='ad'], article",
                {"advertiser": 0, "ad_text": 1, "started": 2,
                 "traffic": 3, "commission_rate": 4}, "dropispy")
        finally:
            b.close()


def src_ixspy():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        pg = b.new_page(user_agent=UA)
        try:
            return _browser_scrape(
                pg, f"https://ixspy.com/search?platform=shopee&keyword={KEYWORD}",
                "table tbody tr, div[class*='product']",
                {"advertiser": 0, "ad_text": 1, "started": 2,
                 "traffic": 3, "commission_rate": 4, "cpc": 5}, "ixspy")
        finally:
            b.close()


# ----------------------------------------------------------------------
# RUNNER
# ----------------------------------------------------------------------
SOURCES = [
    src_meta_ad_library,
    src_tiktok_creative_center,
    src_google_transparency,
    src_bigspy,
    src_dropispy,
    src_ixspy,
]


def main():
    d, t = stamp()
    print("=" * 60)
    print(f"  KEYWORD : {KEYWORD!r}")
    print(f"  LABEL   : {LABEL}")
    print(f"  FILES   : {LABEL}-Ads_({d}_{t}).txt")
    print(f"            {LABEL}-Top-Advertiser_({d}_{t}).txt")
    print(f"            {LABEL}-Top-Ads_({d}_{t}).txt")
    print(f"  COLUMNS : {', '.join(SCHEMA)}")
    print("=" * 60)

    all_rows, per_source = [], {}
    for fn in SOURCES:
        name, rows = safe(fn)
        per_source[name] = rows
        all_rows.extend(rows)

    if not all_rows:
        print("[!] no data from any source.")
        return

    save_rows(all_rows, "Ads")

    counts = {}
    for r in all_rows:
        adv = (r.get("advertiser") or "").strip()
        if not adv:
            continue
        c = counts.setdefault(adv, {"advertiser": adv, "ad_count": 0, "sources": set()})
        c["ad_count"] += 1
        c["sources"].add(r.get("platform", ""))
    top_adv = sorted(
        [row(advertiser=v["advertiser"], ad_count=v["ad_count"],
             sources="|".join(sorted(v["sources"])))
         for v in counts.values()],
        key=lambda x: x.get("ad_count", 0), reverse=True)
    # Top-Advertiser uses its own small schema
    save_top_adv(top_adv)

    top_ads = sorted(all_rows, key=lambda x: len(x.get("ad_text", "")), reverse=True)
    save_rows(top_ads, "Top-Ads")

    print("\n===== SUMMARY =====")
    for name, rows in per_source.items():
        print(f"  {name:<24} {len(rows):>4} rows")
    print(f"  {'TOTAL':<24} {len(all_rows):>4} rows")
    print("Files -> ./output/")


def save_top_adv(rows):
    path = build_name("Top-Advertiser")
    fields = ["keyword", "advertiser", "ad_count", "sources"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows([{k: r.get(k, "") for k in fields} for r in rows])
    print(f"[+] Top-Advertiser: saved {len(rows)} rows -> {path}")


if __name__ == "__main__":
    main()
