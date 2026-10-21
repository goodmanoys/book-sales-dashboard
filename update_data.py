#!/usr/bin/env python3
"""Best-effort monitoring of public book pages; failed checks never overwrite confirmed values."""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / 'data.json'
KY_URL = 'https://product.kyobobook.co.kr/detail/S000221644274'
YES_URL = 'https://www.yes24.com/product/goods/198061595'
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36', 'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8'}


def now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')


def fetch(url):
    r = requests.get(url, headers=UA, timeout=25)
    r.raise_for_status()
    r.encoding = r.apparent_encoding if r.encoding is None else r.encoding
    soup = BeautifulSoup(r.text, 'html.parser')
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()
    txt = re.sub(r'\s+', ' ', soup.get_text(' ', strip=True))
    if '다가설 때와 멈출 때' not in txt:
        raise ValueError('페이지에서 도서 제목을 확인할 수 없음')
    return txt


def parse_yes(text):
    # Some pages contain a tooltip "판매지수란?" immediately after the score.
    patterns = [r'판매지수\s*([\d,]+)(?!\d)', r'판매\s*지수\s*[:：]?\s*([\d,]+)']
    for p in patterns:
        m = re.search(p, text)
        if m:
            v = int(m.group(1).replace(',', ''))
            if 0 <= v <= 10**9:
                return v
    raise ValueError('판매지수를 찾을 수 없음')


def parse_ky(text):
    # Restrict to explicitly labelled ranks. Never confuse price, ratings, or other books' ranks.
    patterns = {
        'kyobo_category': [r'자기계발\s*(?:분야\s*)?(?:주간\s*)?(?:베스트\s*)?(?:셀러\s*)?[:：]?\s*([\d,]+)\s*위', r'([\d,]+)\s*위\s*\(?자기계발\)?'],
        'kyobo_overall': [r'(?:국내도서\s*)?종합\s*(?:주간\s*)?(?:베스트\s*)?(?:셀러\s*)?[:：]?\s*([\d,]+)\s*위', r'([\d,]+)\s*위\s*\(?종합\)?'],
    }
    found = {}
    for key, pats in patterns.items():
        for p in pats:
            m = re.search(p, text)
            if m:
                v = int(m.group(1).replace(',', ''))
                if 1 <= v <= 100000:
                    found[key] = v
                    break
    if not found:
        raise ValueError('교보문고 순위가 페이지에 명시적으로 표시되지 않음(동적 페이지일 수 있음)')
    return found


def main():
    data = json.loads(DATA_FILE.read_text(encoding='utf-8'))
    t = now()
    errors = {}
    fresh = {}
    for source, url, parser in [('kyobo', KY_URL, parse_ky), ('yes24', YES_URL, parse_yes)]:
        try:
            result = parser(fetch(url))
            newvals = result if isinstance(result, dict) else {'yes24_sales': result}
            for k, v in newvals.items():
                data['metrics'][k] = {'value': v, 'checked_at': t, 'origin': source}
                fresh[k] = v
            if source == 'kyobo' and len(newvals) != 2:
                errors['kyobo'] = '두 순위 중 일부만 확인됨; 미확인 값은 이전 확인값 유지'
        except Exception as e:
            errors[source] = f'{type(e).__name__}: {str(e)[:160]}'
    data['run_at'] = t
    data['updated_at'] = t if fresh else data.get('updated_at')
    data['errors'] = errors
    if fresh:
        # History is a timestamped snapshot. Unverified/old fields appear as their last confirmed values.
        data.setdefault('history', []).append({'at': t, **{k: data['metrics'][k]['value'] for k in ('kyobo_category', 'kyobo_overall', 'yes24_sales')}, 'fresh': sorted(fresh)})
        data['history'] = data['history'][-500:]
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'fresh': fresh, 'errors': errors, 'run_at': t}, ensure_ascii=False))
    if not fresh:
        print('No fresh values, existing values preserved.', file=sys.stderr)


if __name__ == '__main__':
    main()
