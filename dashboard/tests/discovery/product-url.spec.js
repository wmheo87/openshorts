import { test, expect } from '@playwright/test';
import { mockApi } from './fixtures';
const assetId='77777777-7777-4777-8777-777777777777';
const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAlgAAAK8CAIAAAC80VYfAAAKoklEQVR4nO3bPXFCARBGUWBwgBb6GKB+BpCFgdQxkD4dJqjSPAXxwM/shHuOgq+7s8Vur7d1AwBVu+kBADBJCAFIE0IA0oQQgDQhBCBNCAFIE0IA0oQQgDQhBCBNCAFIE0IA0oQQgDQhBCBNCAFIE0IA0oQQgDQhBCBNCAFIE0IA0oQQgDQhBCBNCAFIE0IA0oQQgDQhBCBNCAFIE0IA0oQQgDQhBCBNCAFIE0IA0oQQgDQhBCBNCAFIE0IA0oQQgDQhBCBNCAFIE0IA0oQQgDQhBCBNCAFIE0IA0oQQgDQhBCBNCAFIE0IA0oQQgDQhBCBNCAFIE0IA0oQQgDQhBCBNCAFIE0IA0oQQgDQhBCBNCAFIE0IA0oQQgDQhBCBNCAFIE0IA0oQQgDQhBCBNCAFIE0IA0oQQgDQhBCBNCAFIE0IA0oQQgDQhBCBNCAFIE0IA0oQQgDQhBCBNCAFIE0IA0oQQgDQhBCBNCAFIE0IA0oQQgDQhBCBNCAFIE0IA0oQQgDQhBCBNCAFIE0IA0oQQgDQhBCBNCAFIE0IA0oQQgDQhBCBNCAFIE0IA0vbTA3jUx+k8PQHqvr8u0xO4n4sQgDQhBCBNCAFIE0IA0oQQgDQhBCBNCAFI80f4tn5/PqcnwLs5HJfpCTyfixCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDS9tMDeJXDcZmeAPAPuAgBSBNCANKEEIA0IQQgTQgBSBNCANKEEIC07fW2Tm8AgDEuQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCANCEEIE0IAUgTQgDShBCAtD/GhRFyKB2s1wAAAABJRU5ErkJggg==', 'base64');
async function setup(page, {empty=false,error=false}={}) {
  const calls=[];
  await page.addInitScript(()=>{localStorage.setItem('gemini_key','mock-key');localStorage.setItem('os_social_nudge_dismissed','1');});
  await mockApi(page);
  await page.route('**/api/saasshorts/product/**',route=>{
    const req=route.request(),path=new URL(req.url()).pathname;calls.push({path,body:req.postData()?req.postDataJSON():null,headers:req.headers()});
    if(path.endsWith('/providers'))return route.fulfill({json:{providers:[],tts_model:'mock-model'}});
    if(path.endsWith('/url/analyze'))return route.fulfill(error?{status:422,json:{detail:'이 사이트는 공식 API·정책 검증이 필요한 별도 어댑터 대상입니다. 직접 업로드를 사용하세요.'}}:{json:{analysis_id:'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',source_url:'https://shop.example/product',source_site:'shop.example',name:'확인 상품',brand:'실제 브랜드',description:'원문 사양',price:{amount:'12000',currency:'KRW'},features:['재질: 스테인리스'],candidates:empty?[]:[{id:'0',url:'https://media.example/product.png',source_site:'media.example',kind:'image',role:'primary',origin:'jsonld',width:600,height:700,rights_status:'unconfirmed'}]}});
    if(path.endsWith('/url/import'))return route.fulfill({json:{assets:[{id:assetId,kind:'image',duration:0,candidate_id:'0'}],errors:[],imported_candidate_ids:['0']}});
    if(path.endsWith('/assets/'+assetId))return route.fulfill({body:png,contentType:'image/png'});
    if(path.endsWith('/analyze'))return route.fulfill({json:{request_id:req.postDataJSON().request_id,state:'queued'}});
    if(path.includes('/requests/'))return route.fulfill({json:{state:'completed',script:{language:'ko',production_mode:'product',full_narration:'확인된 상품 정보를 살펴보세요',segments:[{asset_id:assetId}]}}});
    return route.fulfill({status:404,json:{detail:'Fixture only'}});
  });
  await page.goto('/#app');
  if(page.viewportSize().width<768)await page.getByRole('button',{name:'메뉴 열기',exact:true}).click();
  await page.getByRole('button',{name:/^AI 쇼츠 제작/}).first().click();return calls;
}
test('product URL rights gate, verified import, private preview and Korean script reuse',async({page})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));const calls=await setup(page);
  await page.getByRole('textbox',{name:'상품 URL 입력',exact:true}).fill('https://shop.example/product');
  await page.getByRole('button',{name:'상품 분석',exact:true}).click();
  const candidate=page.getByRole('article',{name:'자료 후보 1',exact:true});await expect(candidate).toBeVisible();
  await expect(candidate.getByText('사용 권리 미확인',{exact:true})).toBeVisible();
  await page.getByRole('heading',{name:'상품 URL로 자동 제작',exact:true}).scrollIntoViewIfNeeded();
  await page.screenshot({path:test.info().outputPath('url-analysis-rights.png')});
  expect(calls.filter(c=>c.path.endsWith('/url/import'))).toHaveLength(0);
  await candidate.getByRole('checkbox',{name:'제작에 사용할 자료 선택',exact:true}).check();
  const take=page.getByRole('button',{name:'권리 확인한 선택 자료 가져오기',exact:true});await expect(take).toBeDisabled();
  await candidate.getByRole('checkbox',{name:'이 자료의 사용·편집 권리를 확인했습니다',exact:true}).check();await take.click();
  await expect(page.getByLabel('장면 1 내용',{exact:true})).toBeVisible();
  expect(calls.find(c=>c.path.endsWith('/url/import')).body).toEqual({analysis_id:'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',candidate_ids:['0'],rights_confirmed:true});
  await page.getByRole('button',{name:'확인 후 상품 정보를 제작 입력에 적용',exact:true}).click();
  await expect(page.getByLabel('확인된 상품 정보',{exact:true})).toContainText('12000 KRW');
  await page.getByRole('button',{name:'원본 미리보기 불러오기',exact:true}).click();await expect(page.getByRole('img',{name:'장면 1 원본',exact:true})).toBeVisible();
  await page.getByRole('checkbox',{name:/원본 영상·사진·음원의 사용/}).check();
  await page.getByRole('checkbox',{name:/이번 Gemini 유료 요청의 비용/}).check();
  await page.getByRole('button',{name:'제품 대본 생성',exact:true}).click();await expect(page.getByLabel('한국어 내레이션',{exact:true})).toBeVisible();
  const paid=calls.find(c=>c.path.endsWith('/product/analyze'));expect(paid.body.scenes[0].asset_id).toBe(assetId);expect(paid.body.description).toContain('12000 KRW');
  expect(paid.headers).not.toHaveProperty('x-fal-key');expect(paid.headers).not.toHaveProperty('x-elevenlabs-key');expect(errors).toEqual([]);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.screenshot({path:test.info().outputPath('product-url.png')});
});
test('empty media results preserve direct upload and English UI',async({page})=>{
  await setup(page,{empty:true});await page.getByLabel('상품 URL 입력',{exact:true}).fill('https://shop.example/product');await page.getByRole('button',{name:'상품 분석',exact:true}).click();
  await expect(page.getByText('이미지·영상 후보를 찾지 못했습니다. 직접 업로드를 사용하세요.',{exact:true})).toBeVisible();
  await expect(page.getByLabel('제품 영상·사진 업로드',{exact:true})).toBeAttached();
  await page.getByRole('combobox',{name:'화면 언어',exact:true}).selectOption('en-US');
  await expect(page.getByRole('button',{name:'Analyze product',exact:true})).toBeVisible();await expect(page.getByText('No image or video candidates found. Upload your media instead.',{exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});
test('unsupported site gives honest fallback with no imports or paid requests',async({page})=>{
  const calls=await setup(page,{error:true});await page.getByLabel('상품 URL 입력',{exact:true}).fill('https://smartstore.naver.com/example');await page.getByRole('button',{name:'상품 분석',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('별도 어댑터');expect(calls.filter(c=>c.body)).toHaveLength(1);
});
