"""Standard public product metadata only; no marketplace/private API scraping."""
import json
from datetime import datetime, timezone
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from .public_fetch import CollectionError, normalize_url, fetch, check_robots, resolve_public

MAX_PAGE = 2 * 1024 * 1024
MAX_CANDIDATES = 30


def text(value, limit=1500):
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return ''
    value = re.sub(r'<[^>]*>', ' ', str(value))
    return re.sub(r'\s+', ' ', value).strip()[:limit]


def integer(value):
    try:
        return max(0, min(100000, int(value)))
    except (ValueError, TypeError, OverflowError):
        return 0


class ProductHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.images = []
        self.videos = []
        self.jsonld = []
        self.buffer = None
        self.video = False
        self.title = ''
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta':
            name = (attrs.get('property') or attrs.get('name') or '').lower()
            if name:
                self.meta.setdefault(name, []).append(attrs.get('content') or '')
        if tag == 'script' and (attrs.get('type') or '').split(';')[0].strip().lower() == 'application/ld+json':
            self.buffer = []
        if tag == 'title':
            self.in_title = True
        if tag == 'img' and len(self.images) < 100:
            self.images.append({'url': attrs.get('src'), 'width': attrs.get('width'), 'height': attrs.get('height'), 'label': attrs.get('alt', '')})
        if tag == 'video':
            self.video = True
            if attrs.get('src'):
                self.videos.append({'url': attrs['src'], 'label': attrs.get('title', '')})
        if tag == 'source' and self.video and len(self.videos) < 100:
            self.videos.append({'url': attrs.get('src'), 'label': ''})

    def handle_data(self, data):
        if self.buffer is not None:
            self.buffer.append(data)
        if self.in_title:
            self.title += data

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False
        if tag == 'video':
            self.video = False
        if tag == 'script' and self.buffer is not None:
            try:
                self.jsonld.append(json.loads(''.join(self.buffer)))
            except (ValueError, RecursionError):
                pass
            self.buffer = None


def objects(values):
    pending = list(values)
    count = 0
    while pending and count < 2000:
        value = pending.pop(0)
        count += 1
        if isinstance(value, dict):
            yield value
            pending.extend(v for v in value.values() if isinstance(v, (list, dict)))
        elif isinstance(value, list):
            pending.extend(value[:100])


def schema_type(value, name):
    types = value.get('@type', [])
    return any(str(t).rstrip('/').split('/')[-1] == name for t in (types if isinstance(types, list) else [types]))


def extract(html, url):
    parser = ProductHTML()
    try:
        parser.feed(html)
    except (ValueError, RecursionError):
        raise CollectionError('공개 HTML을 해석할 수 없습니다.') from None
    nodes = list(objects(parser.jsonld))
    products = [n for n in nodes if schema_type(n, 'Product')]
    product = products[0] if products else {}
    first = lambda key: next(iter(parser.meta.get(key, [])), '')
    if not products and first('og:type').lower() not in ('product', 'og:product'):
        raise CollectionError('표준 상품 메타데이터가 없거나 동적 페이지라 수집할 수 없습니다. 직접 업로드를 사용하세요.')
    refs = {n.get('@id'): n for n in sorted(nodes, key=len) if isinstance(n.get('@id'), str)}
    def deref(value):
        return refs.get(value.get('@id'), value) if isinstance(value, dict) else value
    brand = deref(product.get('brand', ''))
    brand = brand.get('name', '') if isinstance(brand, dict) else brand
    offers = product.get('offers', [])
    offers = offers if isinstance(offers, list) else [offers]
    prices = set()
    for offer in offers[:50]:
        offer = deref(offer)
        if not isinstance(offer, dict) or schema_type(offer, 'AggregateOffer'):
            continue
        expires = offer.get('priceValidUntil') or offer.get('validThrough')
        if expires:
            try:
                expiry = datetime.fromisoformat(str(expires).replace('Z', '+00:00'))
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                if expiry < datetime.now(timezone.utc):
                    continue
            except ValueError:
                continue
        amount, currency = text(offer.get('price'), 40), text(offer.get('priceCurrency'), 3).upper()
        if re.fullmatch(r'\d{1,15}(?:\.\d{1,4})?', amount) and re.fullmatch('[A-Z]{3}', currency):
            prices.add((amount, currency))
    if not prices:
        amount, currency = first('product:price:amount'), first('product:price:currency').upper()
        if re.fullmatch(r'\d{1,15}(?:\.\d{1,4})?', amount) and re.fullmatch('[A-Z]{3}', currency):
            prices.add((amount, currency))
    price = dict(zip(('amount', 'currency'), next(iter(prices)))) if len(prices) == 1 else None
    features = []
    properties = product.get('additionalProperty', [])
    for prop in (properties if isinstance(properties, list) else [properties])[:15]:
        if isinstance(prop, dict) and text(prop.get('name')) and text(prop.get('value')):
            features.append(text(prop.get('name'), 100) + ': ' + text(prop.get('value'), 200))
    candidates = []
    seen = set()
    def add(value, kind, origin):
        if isinstance(value, list):
            for item in value[:50]:
                add(item, kind, origin)
            return
        if isinstance(value, str):
            value = {'url': value}
        if not isinstance(value, dict):
            return
        raw = value.get('contentUrl') or value.get('url')
        if not isinstance(raw, str) or not raw.strip():
            return
        try:
            source = normalize_url(urljoin(url, raw))
        except ValueError:
            return
        if source in seen or len(candidates) >= MAX_CANDIDATES:
            return
        if re.search(r'logo|banner|advert|로고|배너|광고', text(value.get('label')), re.I):
            return
        if re.search(r'(?:^|[/_.\-])(logo|icon|banner|advert|tracking|sprite|avatar)(?:[/_.\-]|$)', urlsplit(source).path, re.I):
            return
        width, height = integer(value.get('width')), integer(value.get('height'))
        if kind == 'image' and ((width and width < 300) or (height and height < 300) or (width and height and max(width/height, height/width) > 4)):
            return
        seen.add(source)
        candidates.append({'id': str(len(candidates)), 'url': source, 'source_site': urlsplit(source).hostname,
                           'kind': kind, 'role': ('video' if kind == 'video' else 'additional' if any(c['kind'] == 'image' for c in candidates) else 'primary'), 'origin': origin, 'width': width or None, 'height': height or None,
                           'duration_hint': text(value.get('duration'), 50) or None,
                           'rights_status': 'unconfirmed', 'label': text(value.get('name') or value.get('label'), 200)})
    add(product.get('image'), 'image', 'jsonld')
    for node in nodes:
        if schema_type(node, 'VideoObject'):
            # embedUrl is not a downloadable original and is intentionally ignored.
            add({'contentUrl': node.get('contentUrl'), 'name': node.get('name'), 'duration': node.get('duration')}, 'video', 'jsonld')
    for value in parser.meta.get('og:image', []) + parser.meta.get('og:image:secure_url', []) + parser.meta.get('og:image:url', []):
        add(value, 'image', 'opengraph')
    for value in parser.meta.get('og:video', []) + parser.meta.get('og:video:secure_url', []):
        add(value, 'video', 'opengraph')
    for image in parser.images:
        add(image, 'image', 'html')
    for video in parser.videos:
        add(video, 'video', 'html')
    return {'source_url': url, 'source_site': urlsplit(url).hostname, 'adapter': 'public-standard-v1',
            'name': text(product.get('name') or first('og:title') or parser.title, 250), 'brand': text(brand, 150),
            'description': text(product.get('description') or first('og:description')), 'price': price,
            'features': features, 'candidates': candidates,
            'notice': '판매 페이지의 표시 정보이며 사실·가격·이용 권리를 보증하지 않습니다. 수집 성공은 사용 허락이 아닙니다.'}


def analyze(url):
    # Robots policy is checked on every page redirect, including cross-origin ones.
    page = fetch(url, max_bytes=MAX_PAGE, allowed=('text/html', 'application/xhtml+xml'), policy=check_robots)
    result = extract(page.data.decode('utf-8', errors='replace'), page.url)
    hosts = {}
    safe = []
    for candidate in result['candidates']:
        parts = urlsplit(candidate['url'])
        host = (parts.hostname, 443 if parts.scheme == 'https' else 80)
        if host not in hosts:
            if len(hosts) >= 6:
                continue
            try:
                resolve_public(*host)
                hosts[host] = True
            except CollectionError:
                hosts[host] = False
        if hosts[host]:
            safe.append(candidate)
    result['candidates'] = safe
    return result
