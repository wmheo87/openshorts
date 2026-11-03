"""Bounded anonymous public fetches. Pin the validated IP at the TCP layer.

No proxy/env credentials, cookies, JavaScript, browser automation or retries.
Every redirect gets a new all-address DNS check; TLS still verifies hostname.
"""
import concurrent.futures
import http.client
import ipaddress
import fnmatch
import posixpath
import socket
import ssl
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit, quote, parse_qsl, unquote

from security_utils import _ip_is_public

USER_AGENT = 'OpenShortsProductBot/1.0'
DNS_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=4)
UNSUPPORTED = ('coupang.com', 'coupang.net', 'naver.com', 'naver.me', 'pstatic.net')


class CollectionError(ValueError):
    pass


def public_address(value):
    try:
        address = ipaddress.ip_address(value)
        return _ip_is_public(value) and not (address.version == 6 and address.is_site_local)
    except ValueError:
        return False


def normalize_url(value):
    try:
        if not isinstance(value, str) or len(value) > 4096 or any(ord(c) < 33 or ord(c) == 127 for c in value) or '\\' in value:
            raise ValueError()
        parts = urlsplit(value)
        if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username is not None or parts.password is not None:
            raise ValueError()
        if any(key.lower() in ('key', 'api_key', 'apikey', 'access_token', 'token', 'password', 'auth', 'authorization', 'x-amz-signature', 'x-goog-signature') for key, _ in parse_qsl(parts.query)):
            raise ValueError()
        host = parts.hostname.encode('idna').decode('ascii').lower().rstrip('.')
        if '%' in host or parts.port not in (None, 443 if parts.scheme == 'https' else 80):
            raise ValueError()
        if any(host == domain or host.endswith('.' + domain) for domain in UNSUPPORTED):
            raise CollectionError('이 사이트는 공식 API·정책 검증이 필요한 별도 어댑터 대상입니다. 직접 업로드를 사용하세요.')
        try:
            literal = ipaddress.ip_address(host)
        except ValueError:
            literal = None
        if literal and not public_address(host):
            raise ValueError()
        netloc = '[' + host + ']' if ':' in host else host
        return urlunsplit((parts.scheme, netloc, quote(parts.path or '/', safe="/:@-._~!$&'()*+,;=%"), quote(parts.query, safe="/?:@-._~!$&'()*+,;=%"), ''))
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, CollectionError):
            raise
        raise CollectionError('인증 정보가 없는 유효한 공개 HTTP(S) URL만 사용할 수 있습니다.') from None


def resolve_public(host, port):
    future = DNS_POOL.submit(socket.getaddrinfo, host, port, 0, socket.SOCK_STREAM)
    try:
        records = future.result(timeout=5)
    except (OSError, concurrent.futures.TimeoutError):
        future.cancel()
        raise CollectionError('공개 주소 DNS 확인에 실패했습니다.') from None
    addresses = list(dict.fromkeys(record[4][0] for record in records))
    if not addresses or any(not public_address(ip) for ip in addresses):
        raise CollectionError('내부 네트워크 또는 안전하지 않은 주소는 수집하지 않습니다.')
    return addresses[0]


class PinnedConnection(http.client.HTTPConnection):
    def __init__(self, host, port, ip, tls):
        super().__init__(host, port, timeout=8)
        self.ip = ip
        self.tls = tls

    def connect(self):
        # Numeric IP only: the URL hostname is never resolved again by connect.
        self.sock = socket.create_connection((self.ip, self.port), self.timeout)
        if self.sock.getpeername()[0] != self.ip or not public_address(self.sock.getpeername()[0]):
            self.close()
            raise CollectionError('연결 대상 IP 검증에 실패했습니다.')
        if self.tls:
            try:
                self.sock = ssl.create_default_context().wrap_socket(self.sock, server_hostname=self.host)
            except BaseException:
                self.close()
                raise


@dataclass
class Fetched:
    url: str
    mime: str
    data: bytes
    status: int = 200


def fetch(url, *, max_bytes, allowed, seconds=25, allow_missing=False, connection_factory=PinnedConnection, policy=None):
    deadline = time.monotonic() + seconds
    url = normalize_url(url)
    for hop in range(4):
        if policy:
            policy(url)
        parts = urlsplit(url)
        ip = resolve_public(parts.hostname, 443 if parts.scheme == 'https' else 80)
        if time.monotonic() >= deadline:
            raise CollectionError('수집 시간이 초과됐습니다. 직접 업로드를 사용하세요.')
        connection = connection_factory(parts.hostname, 443 if parts.scheme == 'https' else 80, ip, parts.scheme == 'https')
        try:
            connection.request('GET', urlunsplit(('', '', parts.path or '/', parts.query, '')),
                               headers={'User-Agent': USER_AGENT, 'Accept': ', '.join(allowed), 'Accept-Encoding': 'identity', 'Connection': 'close'})
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader('Location')
                if not location or hop == 3:
                    raise CollectionError('리다이렉트가 너무 많거나 올바르지 않습니다.')
                url = normalize_url(urljoin(url, location))
                continue
            if allow_missing and response.status in (404, 410):
                return Fetched(url, '', b'', response.status)
            if response.status != 200:
                raise CollectionError('공개 자료에 접근할 수 없습니다. 인증·차단을 우회하지 않으며 직접 업로드가 가능합니다.')
            mime = (response.getheader('Content-Type') or '').split(';', 1)[0].strip().lower()
            if mime not in allowed or (response.getheader('Content-Encoding') or 'identity').lower() != 'identity':
                raise CollectionError('지원하지 않는 콘텐츠 형식입니다.')
            length = response.getheader('Content-Length')
            if length is not None and (len(length) > 12 or not length.isdigit() or int(length) > max_bytes):
                raise CollectionError('응답 크기 제한을 초과했거나 길이가 올바르지 않습니다.')
            result = bytearray()
            while True:
                if time.monotonic() >= deadline:
                    raise CollectionError('자료 다운로드 시간이 초과됐습니다.')
                chunk = response.read(min(65536, max_bytes + 1 - len(result)))
                if not chunk:
                    break
                result.extend(chunk)
                if len(result) > max_bytes:
                    raise CollectionError('응답 크기 제한을 초과했습니다.')
            if length is not None and int(length) != len(result):
                raise CollectionError('콘텐츠 길이가 일치하지 않습니다.')
            if time.monotonic() > deadline:
                raise CollectionError('자료 다운로드 시간이 초과됐습니다.')
            return Fetched(url, mime, bytes(result))
        except (OSError, http.client.HTTPException):
            raise CollectionError('공개 자료 연결에 실패했습니다. 자동 재시도하지 않습니다.') from None
        finally:
            connection.close()
    raise CollectionError('리다이렉트를 처리할 수 없습니다.')


def check_robots(url, fetcher=fetch):
    parts = urlsplit(normalize_url(url))
    robots_url = urlunsplit((parts.scheme, parts.netloc, '/robots.txt', '', ''))
    response = fetcher(robots_url, max_bytes=65536, allowed=('text/plain',), allow_missing=True)
    if urlsplit(response.url).netloc != parts.netloc:
        raise CollectionError('사이트 수집 정책을 확인할 수 없습니다. 직접 업로드를 사용하세요.')
    if response.status in (404, 410):
        return
    # Conservative robots handling: matching Disallow wins even over Allow.
    # Support wildcards/$ and decoded/dot-normalized paths; never use an
    # exponential backtracking regex for untrusted rules (fnmatch uses atomic
    # groups in Python 3.11+). Specific bot groups take precedence over '*'.
    groups, agents, directives = [], [], []
    for line in response.data.decode('utf-8', errors='replace').splitlines() + ['User-agent: __end__']:
        line = line.split('#', 1)[0].strip()
        if ':' not in line:
            continue
        key, value = (part.strip() for part in line.split(':', 1))
        key = key.lower()
        if key == 'user-agent':
            if directives:
                groups.append((agents, directives))
                agents, directives = [], []
            agents.append(value.lower())
        elif agents:
            directives.append((key, value))
    specific = [(a, d) for a, d in groups if any(agent != '*' and agent and agent in USER_AGENT.lower() for agent in a)]
    applicable = specific or [(a, d) for a, d in groups if '*' in a]
    path = unquote(parts.path or '/')
    query = ('?' + unquote(parts.query)) if parts.query else ''
    normalized_path = posixpath.normpath('/' + path.replace('\\', '/').lstrip('/'))
    if path.endswith('/') and not normalized_path.endswith('/'):
        normalized_path += '/'
    paths = (path + query, normalized_path + query)
    for _, rules in applicable:
        if len(rules) > 200:
            raise CollectionError('사이트 수집 정책을 확인할 수 없습니다. 직접 업로드를 사용하세요.')
        for key, value in rules:
            if key in ('crawl-delay', 'request-rate') and value and value != '0':
                raise CollectionError('사이트 수집 정책에 따라 자동 수집하지 않습니다. 직접 업로드를 사용하세요.')
            if key != 'disallow' or not value:
                continue
            if len(value) > 2048:
                raise CollectionError('사이트 수집 정책을 확인할 수 없습니다. 직접 업로드를 사용하세요.')
            end = value.endswith('$')
            value = unquote(value[:-1] if end else value)
            pattern = ''.join('[?]' if c == '?' else '[[]' if c == '[' else '[]]' if c == ']' else c for c in value)
            if any(fnmatch.fnmatchcase(item, pattern + ('' if end else '*')) for item in paths):
                raise CollectionError('사이트 수집 정책에 따라 자동 수집하지 않습니다. 직접 업로드를 사용하세요.')
