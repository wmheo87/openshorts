import { writeFileSync } from 'node:fs';
import { test, expect } from '@playwright/test';
async function mock(page,billing=false) {
  const calls=[];
  await page.addInitScript(billing=>{localStorage.setItem('gemini_key','fixture-key');localStorage.setItem('uploadPostKey_v3','fixture-post');localStorage.setItem('os_social_nudge_dismissed','1');localStorage.setItem('os_welcomed','1');if(billing)localStorage.setItem('openshorts_auth','fixture-auth');},billing);
  await page.route('**/api/**',route=>{
    const request=route.request(),path=new URL(request.url()).pathname;calls.push({path,method:request.method(),body:request.postData()});
    const responses={
      '/api/config':{billingEnabled:billing,googleAuthEnabled:false,youtubeUrlEnabled:true,jobRetentionSeconds:86400,localLlm:null},
      '/api/me':{user:{id:'fixture-user',email:'user@example.com',name:'Settings'},plan:'creator',entitled:true,minutes:{remaining:300},status:'active'},
      '/api/discovery/history':{items:[],next_before_id:null},'/api/saasshorts/product/providers':{providers:[],tts_model:'gemini-3.8-flash-lite-tts'},
      '/api/saasshorts/tts-model':{catalog_confirmed:false},'/api/saasshorts/actor-gallery':{images:[]},'/api/gallery/videos':{videos:[]},'/api/gallery/actors':{images:[]},
      '/api/history':{videos:[]},'/api/projects':{projects:[]},'/api/autopilot':{enabled:false,channel:null,runs:[],videos:[]},
    };return route.fulfill({json:responses[path]||{items:[],videos:[],profiles:[],images:[]}});
  });return calls;
}
async function navigate(page,name){if(page.viewportSize().width<768)await page.getByRole('button',{name:'메뉴 열기',exact:true}).click();await page.getByRole('button',{name:new RegExp('^'+name)}).first().click();}
test('Korean default and persistent English switch preserve form state',async({page})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));const calls=await mock(page);await page.goto('/#app');
  await expect(page.locator('html')).toHaveAttribute('lang','ko-KR');await expect(page.getByRole('heading',{name:'긴 영상을 쇼츠로 편집하세요',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'영상 URL',exact:true}).click();const input=page.locator('input[placeholder*="https://"]');await input.fill('https://www.youtube.com/watch?v=aaaaaaaaaaa');
  await page.getByRole('combobox',{name:'화면 언어',exact:true}).selectOption('en-US');await expect(page.getByRole('button',{name:'Video URL',exact:true})).toBeVisible();await expect(input).toHaveValue('https://www.youtube.com/watch?v=aaaaaaaaaaa');
  await expect(page.locator('html')).toHaveAttribute('lang','en-US');await page.reload();await expect(page.getByRole('combobox',{name:'Interface language',exact:true})).toHaveValue('en-US');
  expect(calls.filter(c=>c.method==='POST')).toHaveLength(0);expect(errors).toEqual([]);
});
test('major Korean screens and navigation do not overflow',async({page})=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));await mock(page);await page.goto('/#app');
  for(const name of ['AI 쇼츠 제작','영상 찾기','영상 보관함','유튜브 스튜디오','AI 에이전트','설정','쇼츠 편집']){
    await navigate(page,name);await expect(page.getByRole('combobox',{name:'화면 언어',exact:true})).toBeVisible();
    await expect(page.getByRole('heading',{name:/^(Video Discovery|AI Shorts|UGC Gallery|Your Personal Clipping Team|Settings)$/})).toHaveCount(0);
    const size=await page.evaluate(()=>({width:document.documentElement.scrollWidth,viewport:innerWidth}));expect(size.width).toBeLessThanOrEqual(size.viewport+1);
    await page.screenshot({path:test.info().outputPath(name+'.png')});
    writeFileSync(test.info().outputPath(name+'-visible.txt'),await page.locator('main').innerText());
  }expect(errors).toEqual([]);
});
test('conditional history and autopilot are localized; UI locale does not change script language',async({page})=>{
  await mock(page,true);await page.goto('/#app');await navigate(page,'작업 기록');await expect(page.getByRole('heading',{name:'내 보관함',exact:true})).toBeVisible();
  await navigate(page,'자동 제작');await expect(page.getByText('연결된 YouTube 채널이 없습니다',{exact:true})).toBeVisible();
  await navigate(page,'AI 쇼츠 제작');await page.getByRole('button',{name:'AI 배우형 (fal.ai)',exact:true}).click();await expect(page.getByRole('radio',{name:/한국어/})).toHaveAttribute('aria-checked','true');
  await page.getByRole('combobox',{name:'화면 언어',exact:true}).selectOption('en-US');await expect(page.getByRole('radio',{name:/Korean/})).toHaveAttribute('aria-checked','true');await expect(page.getByRole('button',{name:/Low Cost/})).toBeVisible();
});
test('all primary English screens switch back without Korean UI leftovers',async({page})=>{
  const calls=await mock(page,true);await page.goto('/#app');await page.getByRole('combobox',{name:'화면 언어',exact:true}).selectOption('en-US');
  for(const name of ['AI Shorts','Video Discovery','UGC Gallery','YouTube Studio','AI Agent','Settings','History','Autopilot','Clip Generator']){
    if(page.viewportSize().width<768)await page.getByRole('button',{name:'open navigation',exact:true}).click();
    await page.getByRole('button',{name:new RegExp('^'+name)}).first().click();
    await expect(page.getByRole('combobox',{name:'Interface language',exact:true})).toHaveValue('en-US');
    writeFileSync(test.info().outputPath('en-'+name+'.txt'),await page.locator('main').innerText());
    expect((await page.locator('main').innerText()).replaceAll('한국어','')).not.toMatch(/[가-힣]/);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  }
  expect(calls.filter(c=>c.method==='POST')).toHaveLength(0);
});
test('landing, pricing, legal and account pages support both locales',async({page})=>{
  await mock(page,true);
  for(const hash of ['#landing','#/pricing','#legal','#/account']){
    await page.goto('/'+hash);const selector=page.getByRole('combobox',{name:'화면 언어',exact:true});await expect(selector).toBeVisible();
    writeFileSync(test.info().outputPath('ko-'+hash.replaceAll('/','-')+'.txt'),await page.locator('body').innerText());
    await selector.selectOption('en-US');await expect(page.getByRole('combobox',{name:'Interface language',exact:true})).toBeVisible();
    writeFileSync(test.info().outputPath('en-'+hash.replaceAll('/','-')+'.txt'),await page.locator('body').innerText());
    expect((await page.locator('body').innerText()).replaceAll('한국어','')).not.toMatch(/[가-힣]/);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
    await page.getByRole('combobox',{name:'Interface language',exact:true}).selectOption('ko-KR');
  }
});
test('invalid saved UI locale falls back to Korean and keeps user metadata verbatim',async({page})=>{
  await mock(page);await page.addInitScript(()=>localStorage.setItem('openshorts_ui_locale','es-ES'));
  const { videos,searchResponse }=await import('./fixtures');
  await page.route('**/api/discovery/search',route=>route.fulfill({json:searchResponse([{...videos[0],title:'Settings',channel_title:'History',description:'Generate Clips'}])}));
  await page.goto('/#app?tab=discovery');await expect(page.locator('html')).toHaveAttribute('lang','ko-KR');
  await page.getByLabel('검색어',{exact:true}).fill('Settings');await page.getByRole('button',{name:'영상 검색',exact:true}).click();
  const article=page.getByRole('article',{name:'Settings',exact:true});await expect(article.getByText('Settings',{exact:true})).toBeVisible();
  await page.getByRole('combobox',{name:'화면 언어',exact:true}).selectOption('en-US');
  await expect(article.getByText('Settings',{exact:true})).toBeVisible();await expect(article.getByRole('button',{name:'Settings Select video',exact:true})).toBeVisible();
  await expect(page.getByRole('searchbox')).toHaveValue('Settings');
});
