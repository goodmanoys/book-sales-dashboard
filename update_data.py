#!/usr/bin/env python3
"""Best-effort book metrics collection. Never replace a verified number on failure.

Kyobo: HTTP first, then browser rendering when HTTP does not expose ranking.
YES24: HTTP. No invented rank, no guessed index.
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

BASE = Path(__file__).resolve().parent
STORE = BASE / 'data.json'
KY_URL = 'https://product.kyobobook.co.kr/detail/S000221644274'
YES_URL = 'https://www.yes24.com/product/goods/198061595'
TITLE = '다가설 때와 멈출 때'
HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/128.0.0.0 Safari/537.36'),
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8',
}


def now():
    return datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')


def normalized(text):
    return re.sub(r'\s+', '', text)


def valid_title(text):
    return normalized(TITLE) in normalized(text)


def fetch_http(url):
    r = requests.get(url, timeout=30, headers=HEADERS)
    r.raise_for_status()
    soup = BeautifulSoup(r.content, 'html.parser')
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()
    text = re.sub(r'\s+', ' ', soup.get_text(' ', strip=True))
    if not valid_title(text):
        raise ValueError(f'HTTP {r.status_code}: 본문에서 대상 도서 제목을 확인하지 못함')
    return text


def fetch_browser(url):
    """Try a genuine browser for pages hydrated by JavaScript; not guaranteed against blocking."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
        try:
            context = browser.new_context(
                locale='ko-KR', timezone_id='Asia/Seoul',
                user_agent=HEADERS['User-Agent'],
                viewport={'width': 1365, 'height': 920},
            )
            page = context.new_page()
            page.goto(url, wait_until='domcontentloaded', timeout=35000)
            page.wait_for_timeout(4500)
            text = page.locator('body').inner_text(timeout=12000)
            if not valid_title(text):
                raise ValueError(f'브라우저에서도 대상 도서 제목이 확인되지 않음 (URL: {page.url})')
            return re.sub(r'\s+', ' ', text)
        finally:
            browser.close()


def parse_yes(text):
    # The sales index should explicitly follow its own label.
    match = re.search(r'판매\s*지수\s*[:：]?\s*([\d,]+)(?!\d)', text)
    if not match:
        raise ValueError('YES24 판매지수를 확인하지 못함')
    value = int(match.group(1).replace(',', ''))
    if not 0 <= value <= 1000000000:
        raise ValueError('YES24 판매지수 값 범위 오류')
    return value


def parse_ky(text):
    # Match only explicitly labelled rankings shown near the title's 주간베스트 badge.
    # A broad search would risk collecting unrelated rankings farther down the page.
    compact = re.sub(r'\s+', ' ', text)
    pos = compact.find(TITLE)
    if pos < 0:
        raise ValueError('교보문고 도서 제목 미확인')
    excerpt = compact[pos:pos + 1800]
    badge = excerpt.find('주간베스트')
    if badge == -1:
        raise ValueError('교보문고 주간베스트 표시를 찾지 못함')
    segment = excerpt[badge:badge + 450].split('구매혜택')[0].split('기본정보')[0]
    labels = {
        'kyobo_category': '자기계발',
        'kyobo_overall': r'(?:국내\s*도서|국내도서\s*종합|종합)',
    }
    results = {}
    for key, label in labels.items():
        for pattern in (
            rf'(?:{label})\s*[:：]?\s*(\d{{1,5}}(?:,\d{{3}})?)\s*위',
            rf'(\d{{1,5}}(?:,\d{{3}})?)\s*위\s*(?:{label})',
        ):
            found = re.search(pattern, segment)
            if found:
                rank = int(found.group(1).replace(',', ''))
                if 1 <= rank <= 100000:
                    results[key] = rank
                    break
    if not results:
        raise ValueError('주간베스트 영역에 유효한 국내도서/자기계발 순위 없음')
    return results


def check_kyobo():
    diagnostics = []
    found = {}
    # Preserve any partial HTTP success and use a browser to fill missing metrics.
    for name, fetcher in [('HTTP', fetch_http), ('브라우저', fetch_browser)]:
        if name == '브라우저' and len(found) == 2:
            break
        try:
            new = parse_ky(fetcher(KY_URL))
            found.update(new)
        except Exception as exc:
            diagnostics.append(f'{name}: {type(exc).__name__}: {str(exc)[:150]}')
    if len(found) == 2:
        return found, None
    absent = sorted({'kyobo_category', 'kyobo_overall'} - found.keys())
    diagnostics.append('미확인: ' + ', '.join(absent))
    return found, ' | '.join(diagnostics)


def main():
    data = json.loads(STORE.read_text(encoding='utf-8'))
    t = now()
    fresh = {}
    errors = {}

    kyobo, kyobo_error = check_kyobo()
    fresh.update(kyobo)
    if kyobo_error:
        errors['kyobo'] = kyobo_error

    try:
        fresh['yes24_sales'] = parse_yes(fetch_http(YES_URL))
    except Exception as exc:
        errors['yes24'] = f'{type(exc).__name__}: {str(exc)[:160]}'

    for key, value in fresh.items():
        data['metrics'][key] = {
            'value': value,
            'checked_at': t,
            'origin': 'kyobo' if key.startswith('kyobo_') else 'yes24',
        }
    data['run_at'] = t
    data['updated_at'] = t if fresh else data.get('updated_at')
    data['errors'] = errors
    if fresh:
        # Snapshot lists fresh fields; unchanged fields retain last confirmed value.
        data.setdefault('history', []).append({
            'at': t,
            **{k: data['metrics'][k]['value']
               for k in ('kyobo_category', 'kyobo_overall', 'yes24_sales')},
            'fresh': sorted(fresh),
        })
        data['history'] = data['history'][-500:]
    STORE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'fresh': fresh, 'errors': errors, 'run_at': t}, ensure_ascii=False))
    if not fresh:
        print('No fresh values; previous values preserved.', file=sys.stderr)


if __name__ == '__main__':
    main()
