"""No paid APIs or external downloads. Public transport and owned media fixtures."""
import asyncio
import io
import json
import socket
import time
from types import SimpleNamespace as NS

import httpx
import pytest
from fastapi import FastAPI
from PIL import Image

import app as engine
from studio.product_video import api, product_page as page, public_fetch as net, storage, url_api


def html(images=None, **fields):
    product = {'@context': 'https://schema.org', '@type': 'Product', 'name': '한국 상품',
               'brand': {'name': '확인 브랜드'}, 'description': '<b>실제 설명</b>',
               'offers': {'@type': 'Offer', 'price': '12000', 'priceCurrency': 'KRW'},
               'image': images if images is not None else ['/main.png', '/main.png#duplicate'], **fields}
    return '<script type="application/ld+json">'+json.dumps(product, ensure_ascii=False)+'</script>'


def photo(size=(600, 700)):
    stream = io.BytesIO()
    Image.new('RGB', size, '#abccdd').save(stream, format='PNG')
    return stream.getvalue()


def test_jsonld_graph_metadata_and_deduplication():
    content = html(additionalProperty=[{'name': '재질', 'value': '스테인리스'}]) + '<img src="/logo.png"><img src="/small.png" width="20" height="20"><video><source src="/demo.mp4"></video>'
    result = page.extract(content, 'https://shop.example/item')
    assert result['name'] == '한국 상품' and result['brand'] == '확인 브랜드'
    assert result['description'] == '실제 설명'
    assert result['price'] == {'amount': '12000', 'currency': 'KRW'}
    assert result['features'] == ['재질: 스테인리스']
    assert [c['url'] for c in result['candidates']] == ['https://shop.example/main.png', 'https://shop.example/demo.mp4']
    assert all(c['rights_status'] == 'unconfirmed' for c in result['candidates'])
    graph = '<script type="application/ld+json">'+json.dumps({'@graph':[{'@type':'Product','name':'Graph','offers':{'@id':'#offer'}},{'@id':'#offer','@type':'Offer','price':'9.95','priceCurrency':'USD'}]})+'</script>'
    assert page.extract(graph, 'https://shop.example/')['price']['currency'] == 'USD'


def test_opengraph_empty_media_and_invalid_json_are_honest():
    result = page.extract('<script type="application/ld+json">broken</script><meta property="og:type" content="product"><meta property="og:title" content="OG"><meta property="product:price:amount" content="42.00"><meta property="product:price:currency" content="USD">', 'https://shop.example/')
    assert result['name'] == 'OG' and result['price']['amount'] == '42.00' and result['candidates'] == []
    with pytest.raises(net.CollectionError):
        page.extract('<div>Javascript app or sign in</div>', 'https://shop.example/')


def test_no_invented_price_review_or_aggregate_discount():
    for offers in [{'@type':'AggregateOffer','lowPrice':'20','priceCurrency':'KRW'}, [{'price':'20','priceCurrency':'KRW'},{'price':'30','priceCurrency':'KRW'}], {'price':'free','priceCurrency':'KRW'}]:
        result = page.extract(html(offers=offers), 'https://shop.example/')
        assert result['price'] is None
        assert 'reviews' not in result and 'discount' not in result


@pytest.mark.parametrize('url', ['file:///etc/passwd','http://127.0.0.1','http://[::1]','http://169.254.169.254','http://100.64.0.1','http://[fec0::1]','http://[::ffff:127.0.0.1]','http://localhost:8000','https://user:secret@example.com/','https://example.com\\@127.0.0.1/', 'https://example.com/%0d\nHost:x', 'https://shop.coupang.com/product', 'https://smartstore.naver.com/item'])
def test_invalid_internal_or_unsupported_urls(url):
    with pytest.raises(net.CollectionError):
        net.normalize_url(url)


def test_mixed_dns_and_rebinding_fail_closed(monkeypatch):
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a: [(socket.AF_INET,socket.SOCK_STREAM,6,'',('8.8.8.8',443)),(socket.AF_INET,socket.SOCK_STREAM,6,'',('10.0.0.1',443))])
    with pytest.raises(net.CollectionError):
        net.resolve_public('shop.example',443)


class Response:
    def __init__(self, data=b'ok', status=200, **headers):
        self.status=status; self.headers={'Content-Type':'text/html',**headers}; self.stream=io.BytesIO(data)
    def getheader(self, name): return self.headers.get(name)
    def read(self, size): return self.stream.read(size)


class Connection:
    responses=[]
    opened=[]
    def __init__(self,*args): self.opened.append(args)
    def request(self,*args,**kw): self.request_data=(args,kw)
    def getresponse(self): return self.responses.pop(0)
    def close(self): pass


def test_redirect_ip_recheck_size_mime_and_timeout(monkeypatch):
    monkeypatch.setattr(net,'resolve_public',lambda *a:'8.8.8.8')
    Connection.responses=[Response(status=302,Location='http://127.0.0.1/private')]
    with pytest.raises(net.CollectionError):net.fetch('https://shop.example/',max_bytes=10,allowed=('text/html',),connection_factory=Connection)
    for response in [Response(b'01234567890'),Response(**{'Content-Length':'100'}),Response(**{'Content-Length':'3'}),Response(**{'Content-Type':'application/json'}),Response(**{'Content-Encoding':'gzip'}),Response(status=403),Response(status=429)]:
        Connection.responses=[response]
        with pytest.raises(net.CollectionError):net.fetch('https://shop.example/',max_bytes=10,allowed=('text/html',),connection_factory=Connection)
    checked=[]
    def dns(host,port):
        checked.append(host)
        if len(checked)>1:raise net.CollectionError('rebinding')
        return '8.8.8.8'
    monkeypatch.setattr(net,'resolve_public',dns)
    Connection.responses=[Response(status=302,Location='/again')]
    with pytest.raises(net.CollectionError):net.fetch('https://shop.example/',max_bytes=10,allowed=('text/html',),connection_factory=Connection)
    assert checked==['shop.example','shop.example']
    monkeypatch.setattr(net,'resolve_public',lambda *a:'8.8.8.8')
    with pytest.raises(net.CollectionError):net.fetch('https://shop.example/',max_bytes=10,allowed=('text/html',),seconds=-1,connection_factory=Connection)


def test_pinned_connection_uses_numeric_address_and_tls_hostname(monkeypatch):
    connected=[]
    sock=NS(getpeername=lambda:('8.8.8.8',443),close=lambda:None)
    monkeypatch.setattr(net.socket,'create_connection',lambda address,timeout:connected.append(address) or sock)
    tls=[]
    monkeypatch.setattr(net.ssl,'create_default_context',lambda:NS(wrap_socket=lambda sock,server_hostname:tls.append(server_hostname) or sock))
    net.PinnedConnection('shop.example',443,'8.8.8.8',True).connect()
    assert connected==[('8.8.8.8',443)] and tls==['shop.example']


def test_robots_denial_and_no_auth_bypass():
    def robots(*a,**k):return net.Fetched('https://shop.example/robots.txt','text/plain',b'User-agent: *\nDisallow: /private')
    with pytest.raises(net.CollectionError):net.check_robots('https://shop.example/private/item',robots)
    net.check_robots('https://shop.example/public/item',robots)


@pytest.fixture
def product_app(tmp_path,monkeypatch):
    monkeypatch.setattr(engine,'UPLOAD_DIR',str(tmp_path))
    monkeypatch.setattr(engine,'BILLING_ENABLED',False)
    app=FastAPI();app.include_router(api.create_router(engine))
    return app


async def request(app,path,body):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        return await client.post('/api/saasshorts/product'+path,json=body)


def test_rights_before_download_and_idempotent_asset_integration(product_app,monkeypatch):
    monkeypatch.setattr(page,'analyze',lambda url:page.extract(html(),url))
    calls=[]
    monkeypatch.setattr(net,'fetch',lambda url,**kw:calls.append(url) or net.Fetched(url,'image/png',photo()))
    async def run():
        analyzed=await request(product_app,'/url/analyze',{'url':'https://shop.example/item'})
        assert analyzed.status_code==200
        data=analyzed.json(); assert calls==[]
        payload={'analysis_id':data['analysis_id'],'candidate_ids':['0']}
        assert (await request(product_app,'/url/import',payload)).status_code==400
        assert calls==[]
        payload['rights_confirmed']=True
        first=await request(product_app,'/url/import',payload)
        assert first.status_code==200,first.text
        asset=first.json()['assets'][0];assert asset['approved'] and asset['width']==600
        assert 'path' not in asset and 'user_id' not in asset
        second=await request(product_app,'/url/import',payload)
        assert second.json()['assets'][0]['id']==asset['id'] and len(calls)==1
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=product_app),base_url='http://test') as client:
            assert (await client.get('/api/saasshorts/product/assets/'+asset['id'])).content==photo()
        meta=json.loads((storage.root(engine)/asset['id']/'meta.json').read_text())
        assert meta['source_url']=='https://shop.example/main.png' and meta['rights_confirmed_at']
    asyncio.run(run())


def test_wrong_type_expiry_unknown_candidate_and_owner(product_app,monkeypatch):
    monkeypatch.setattr(page,'analyze',lambda url:page.extract(html(),url))
    monkeypatch.setattr(net,'fetch',lambda url,**kw:net.Fetched(url,'image/png',b'<html>not media</html>'))
    async def run():
        data=(await request(product_app,'/url/analyze',{'url':'https://shop.example/'})).json()
        payload={'analysis_id':data['analysis_id'],'candidate_ids':['0'],'rights_confirmed':True}
        bad=await request(product_app,'/url/import',payload)
        assert not bad.json()['assets'] and bad.json()['errors']
        assert (await request(product_app,'/url/import',{**payload,'candidate_ids':['9']})).status_code==422
        async def deny(*args):raise engine.HTTPException(404,'Not found')
        with monkeypatch.context() as m:
            m.setattr(engine,'_assert_job_owner',deny)
            assert (await request(product_app,'/url/import',payload)).status_code==404
        meta=storage.root(engine)/data['analysis_id']/'meta.json'
        stored=json.loads(meta.read_text());stored['created_at']=time.time()-storage.TTL-1;meta.write_text(json.dumps(stored))
        assert (await request(product_app,'/url/import',payload)).status_code==410
    asyncio.run(run())


@pytest.mark.parametrize('mime,data', [('image/jpeg',photo()),('image/png',photo((100,100))),('image/png',photo((1500,300))),('video/mp4',b'not-an-mp4'),('image/svg+xml',b'<svg/>')])
def test_media_type_magic_and_quality(mime,data):
    with pytest.raises(net.CollectionError):url_api.media_kind(net.Fetched('https://shop.example/file',mime,data))


def test_analysis_revalidates_candidate_hosts_and_caps_candidates(monkeypatch):
    content=html(images=['https://internal.example/x.png','https://cdn.example/ok.png']+[f'/p{i}.png' for i in range(50)])
    monkeypatch.setattr(page,'fetch',lambda *a,**k:net.Fetched('https://shop.example/item','text/html',content.encode()))
    checked=[]
    def resolve(host,port):
        checked.append(host)
        if host=='internal.example':raise net.CollectionError('private')
        return '8.8.8.8'
    monkeypatch.setattr(page,'resolve_public',resolve)
    result=page.analyze('https://shop.example/item')
    assert not any(c['source_site']=='internal.example' for c in result['candidates'])
    assert len(result['candidates'])<=30 and checked.count('shop.example')==1


def test_duplicate_content_one_asset_and_request_budget(product_app,monkeypatch):
    monkeypatch.setattr(page,'analyze',lambda url:page.extract(html(images=['/one.png','/two.png']),url))
    monkeypatch.setattr(net,'fetch',lambda url,**kw:net.Fetched(url,'image/png',photo()))
    async def run():
        data=(await request(product_app,'/url/analyze',{'url':'https://shop.example/'})).json()
        result=(await request(product_app,'/url/import',{'analysis_id':data['analysis_id'],'candidate_ids':['0','0','1'],'rights_confirmed':True})).json()
        assert len(result['assets'])==1 and result['imported_candidate_ids']==['0','1']
        for _ in range(8):
            assert (await request(product_app,'/url/analyze',{'url':'https://shop.example/'})).status_code==200
        assert (await request(product_app,'/url/analyze',{'url':'https://shop.example/'})).status_code==429
    asyncio.run(run())


def test_policy_on_each_redirect_and_no_credentials(monkeypatch):
    monkeypatch.setattr(net,'resolve_public',lambda *a:'8.8.8.8')
    Connection.responses=[Response(status=302,Location='https://cdn.example/image'),Response(b'ok',**{'Content-Length':'2'})]
    policies=[]
    result=net.fetch('https://shop.example/',max_bytes=10,allowed=('text/html',),connection_factory=Connection,policy=policies.append)
    assert result.data==b'ok' and policies==['https://shop.example/','https://cdn.example/image']


def test_url_import_real_ffmpeg_korean_subtitles_and_private_download(product_app,monkeypatch,tmp_path):
    import shutil,subprocess,uuid
    from studio.product_video import render
    import saasshorts
    if not shutil.which('ffmpeg'):pytest.skip('FFmpeg required')
    monkeypatch.setattr(page,'analyze',lambda url:page.extract(html(),url))
    monkeypatch.setattr(net,'fetch',lambda url,**kw:net.Fetched(url,'image/png',photo()))
    monkeypatch.setenv('GEMINI_API_KEY','mock-key')
    monkeypatch.setattr(api.gemini_tts,'verify_model',lambda *a:{'model':'mock'})
    monkeypatch.setattr(render,'ensure_runtime',lambda:None)
    def voice(text,key,output,*args):
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=440:duration=24','-ar','24000',output],check=True,capture_output=True)
        return output
    monkeypatch.setattr(render,'generate_voiceover',voice)
    monkeypatch.setattr(saasshorts,'transcribe_audio_for_subs',lambda *a,**k:[{'word':'확인된상품정보','start':0,'end':23.8}])
    async def run():
        data=(await request(product_app,'/url/analyze',{'url':'https://shop.example/'})).json()
        asset=(await request(product_app,'/url/import',{'analysis_id':data['analysis_id'],'candidate_ids':['0'],'rights_confirmed':True})).json()['assets'][0]
        ident=str(uuid.uuid4())
        body={'request_id':ident,'scenes':[{'asset_id':asset['id'],'duration':3,'motion':'pan'}],
              'description':'확인된 상품 정보','rights_confirmed':True,'paid_confirmed':True,'content_confirmed':True,
              'script':{'production_mode':'product','language':'ko','full_narration':'확인된 상품 정보를 살펴보세요','segments':[{'asset_id':asset['id']}]}}
        response=await request(product_app,'/generate',body)
        assert response.status_code==200,response.text
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=product_app),base_url='http://test') as client:
            for _ in range(600):
                status=(await client.get('/api/saasshorts/product/requests/'+ident)).json()
                if status['state'] in ('completed','failed'):break
                await asyncio.sleep(.1)
            assert status['state']=='completed',status
            downloaded=await client.get('/api/saasshorts/product/download/'+ident)
            assert downloaded.status_code==200 and len(downloaded.content)>1000
        folder=storage.root(engine)/('job_'+ident)
        streams,duration=storage.probe(folder/'product.mp4')
        assert 23.8<=duration<=24.5 and any(s.get('width')==720 and s.get('height')==1280 for s in streams)
        assert '확인된상품정보' in (folder/'captions.ass').read_text()
    asyncio.run(run())


@pytest.mark.parametrize('url',['https://shop.example/?api_key=secret','https://cdn.example/item?X-Amz-Signature=private'])
def test_credential_query_not_accepted_or_reflected(url):
    with pytest.raises(net.CollectionError) as error:net.normalize_url(url)
    assert 'secret' not in str(error.value) and 'private' not in str(error.value)


def test_expired_offer_is_not_presented_as_current():
    result=page.extract(html(offers={'@type':'Offer','price':'12000','priceCurrency':'KRW','priceValidUntil':'2000-01-01'}),'https://shop.example/')
    assert result['price'] is None


def test_download_deadline_during_stream_and_oversized_header(monkeypatch):
    monkeypatch.setattr(net,'resolve_public',lambda *a:'8.8.8.8')
    clock=[0]
    monkeypatch.setattr(net,'time',NS(monotonic=lambda:clock[0]))
    class Slow(Response):
        def read(self,size):
            clock[0]+=20
            return super().read(size)
    Connection.responses=[Slow(b'ok')]
    with pytest.raises(net.CollectionError):net.fetch('https://shop.example/',max_bytes=10,allowed=('text/html',),seconds=10,connection_factory=Connection)
    clock[0]=0;Connection.responses=[Response(**{'Content-Length':'9'*5000})]
    with pytest.raises(net.CollectionError):net.fetch('https://shop.example/',max_bytes=10,allowed=('text/html',),connection_factory=Connection)


def test_malformed_public_tags_do_not_discard_valid_product_metadata():
    result=page.extract(html(images=['http://[invalid/','/valid.png'])+'<meta property="og:image" content><script type></script>','https://shop.example/')
    assert result['name']=='한국 상품'
    assert [candidate['url'] for candidate in result['candidates']]==['https://shop.example/valid.png']


def test_robots_wildcards_allow_conflicts_and_encoded_dot_paths():
    def robots(*a,**k):return net.Fetched('https://shop.example/robots.txt','text/plain',b'User-agent: *\nAllow: /\nDisallow: /private*\nDisallow: /blocked/\nDisallow: /*?secret=*')
    for path in ['/private/item','/%70rivate/item','/safe/../private','/item?secret=1','//blocked/','/safe/%2e%2e/blocked/']:
        with pytest.raises(net.CollectionError):net.check_robots('https://shop.example'+path,robots)
    net.check_robots('https://shop.example/public/item',robots)


def test_video_url_import_checks_type_then_probes_duration_and_private_preview(product_app,monkeypatch,tmp_path):
    import shutil,subprocess
    if not shutil.which('ffmpeg'):pytest.skip('FFmpeg required')
    original=tmp_path/'owned-original.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=navy:s=160x120:d=2:r=30','-c:v','libx264','-pix_fmt','yuv420p',str(original)],check=True,capture_output=True)
    monkeypatch.setattr(page,'analyze',lambda url:page.extract(html(images=[],video={'@type':'VideoObject','contentUrl':'https://cdn.example/video.mp4','duration':'PT2S'}),url))
    responses=[net.Fetched('https://cdn.example/not-video','image/png',photo()),net.Fetched('https://final.example/original.mp4','video/mp4',original.read_bytes())]
    monkeypatch.setattr(net,'fetch',lambda *a,**k:responses.pop(0))
    async def run():
        data=(await request(product_app,'/url/analyze',{'url':'https://shop.example/'})).json()
        assert data['candidates'][0]['kind']=='video' and data['candidates'][0]['duration_hint']=='PT2S'
        payload={'analysis_id':data['analysis_id'],'candidate_ids':['0'],'rights_confirmed':True}
        rejected=(await request(product_app,'/url/import',payload)).json()
        assert not rejected['assets'] and '타입' in rejected['errors'][0]['message']
        result=(await request(product_app,'/url/import',payload)).json()['assets'][0]
        assert result['kind']=='video' and 1.9<result['duration']<2.1
        assert result['source_site']=='final.example'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=product_app),base_url='http://test') as client:
            preview=await client.get('/api/saasshorts/product/assets/'+result['id'])
            assert preview.headers['content-type'].startswith('video/mp4') and preview.content==original.read_bytes()
    asyncio.run(run())
