/* User-click, current DOM only. No background requests, cookies, tracking, or remote upload. */
const button = document.getElementById('collect');
const status = document.getElementById('status');
document.getElementById('consent').addEventListener('change', e => { button.disabled = !e.target.checked; });
function extractCoupang() {
  const page = new URL(location.href);
  if (page.hostname !== 'www.coupang.com' || !/^\/vp\/products\/\d+/.test(page.pathname)) {
    throw new Error('쿠팡 상품 상세페이지에서 실행해 주세요.');
  }
  const root = document.querySelector('.product-detail-content-inside');
  const imageUrl = img => {
    try {
      const url = new URL(img.currentSrc || img.getAttribute('src') || '', location.href);
      return url.protocol === 'https:' && (url.hostname === 'coupangcdn.com' || url.hostname.endsWith('.coupangcdn.com')) ? url.href : null;
    } catch { return null; }
  };
  const unique = list => [...new Map(list.filter(x => x.url).map(x => [x.url, x])).values()];
  const gallery = unique([...document.querySelectorAll('.product-image img')].map(img => {
    const url = imageUrl(img);
    // URL substitutions are only candidates; they are NOT validated downloads.
    const candidate = url?.replace(/\/48x48(?:q\d+)?ex\//, '/640x640ex/');
    return { url, high_res_candidate: candidate === url ? null : candidate,
      width: img.naturalWidth, height: img.naturalHeight, category: 'gallery' };
  }));
  const details = unique([...(root?.querySelectorAll('img') || [])].map(img => ({
    url: imageUrl(img), width: img.naturalWidth, height: img.naturalHeight,
    loaded: img.complete && img.naturalWidth > 0, category: 'detail'
  })));
  const reviews = [...document.querySelectorAll('article')].map(article => {
    const body = article.querySelector('div.twc-break-all')?.innerText?.trim() || '';
    if (body.length < 10) return null;
    // Do not harvest author names, profile identifiers, or review photos.
    return { body: body.slice(0, 5000), excerpt: body.slice(0, 160) };
  }).filter(Boolean).slice(0, 50);
  const title = document.querySelector('h1')?.innerText?.trim()?.slice(0, 300) || '';
  return { schema_version: 1, source: 'coupang-dom', product_url: page.origin + page.pathname + '?itemId=' + (page.searchParams.get('itemId') || ''),
    captured_at: new Date().toISOString(), title, images: { gallery, details }, reviews,
    notes: ['브라우저에 현재 렌더된 데이터만 포함', '이미지 URL은 참조 후보이며 사용 권한 또는 실제 다운로드를 보장하지 않음',
      '리뷰는 현재 DOM의 일부 표본이며 전체 리뷰나 대표성 있는 통계가 아님'] };
}
button.addEventListener('click', async () => {
  button.disabled = true;
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.url || new URL(tab.url).hostname !== 'www.coupang.com') throw new Error('쿠팡 상품페이지 탭을 선택하세요.');
    const results = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: extractCoupang });
    const data = results[0]?.result;
    if (!data) throw new Error('페이지 정보를 찾지 못했습니다.');
    const blob = new Blob([JSON.stringify(data, null, 2)], {type:'application/json'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url; link.download = 'openshorts-coupang-' + new URL(data.product_url).pathname.split('/').pop() + '.json';
    document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url);
    status.textContent = '완료: 갤러리 ' + data.images.gallery.length + '개, 상세 ' + data.images.details.length +
      '개, 현재 보이는 리뷰 ' + data.reviews.length + '개. JSON을 OpenShorts 제품 영상형에서 불러오세요.';
  } catch(e) { status.textContent = '실패: ' + (e.message || String(e)); }
  finally { button.disabled = !document.getElementById('consent').checked; }
});
