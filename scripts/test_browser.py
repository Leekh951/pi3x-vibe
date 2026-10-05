from chrome_cdp import CDP
import json
c=CDP();c.call('Page.enable');c.call('Runtime.enable')
c.call('Page.reload',{'ignoreCache':True})
c.js('new Promise(resolve=>setTimeout(resolve,600))')
script=r'''(async()=>{
 const results=[]; const check=(name,condition)=>{results.push({name,pass:!!condition});if(!condition)throw Error('FAIL: '+name);};
 const T=window.spaceTest,S=T.state,V=S.viewer,$=id=>document.getElementById(id);
 check('WebGL renders',document.documentElement.dataset.ready==='true'&&V.renderer.domElement.width>0);
 check('Synthetic demo labelled', $('engine-label').textContent.includes('합성')&&V.data.confidence.length>100000);
 $('view-top').click();check('Top view',V.camera.position.y>V.camera.position.x&&$('view-top').getAttribute('aria-pressed')==='true');
 $('view-perspective').click();$('auto-rotate').click();check('Auto rotate',V.controls.autoRotate);$('reset-view').click();check('Reset stops rotation',!V.controls.autoRotate);
 $('point-size').value='4';$('point-size').dispatchEvent(new Event('input'));check('Point size',V.material.uniforms.pointSize.value===4*V.renderer.getPixelRatio());
 document.querySelector('[data-color="height"]').click();check('Height shading',V.material.uniforms.colorMode.value===1);document.querySelector('[data-color="original"]').click();
 const before=V.data.confidence.length;$('confidence').value='80';$('confidence').dispatchEvent(new Event('input'));check('Confidence filters points',Number($('point-count').textContent.replaceAll(',',''))<before);
 const exported=await V.exportPLY().arrayBuffer();const roundtrip=V.parsePLY(exported);check('Binary PLY round trip',roundtrip.hasConfidence&&roundtrip.count<before&&V.coordinateSystem==='Y_UP');
 $('confidence').value='10';$('confidence').dispatchEvent(new Event('input'));T.showDemo();
 const plain='ply\nformat ascii 1.0\nelement vertex 3\nproperty float x\nproperty float y\nproperty float z\nproperty uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n0 0 0 255 0 0\n1 1 1 0 255 0\n2 2 2 0 0 255\n';
 check('ASCII PLY without confidence',V.parsePLY(new TextEncoder().encode(plain).buffer).hasConfidence===false);
 let rejected=false;try{V.parsePLY(new TextEncoder().encode('not a ply').buffer);}catch{rejected=true;}check('Invalid PLY rejected',rejected);T.showDemo();
 check('Endpoint normalized',T.normalizeEndpoint('https://unit-test.gradio.live/')==='https://unit-test.gradio.live');
 for(const url of ['javascript:alert(1)','http://unit-test.gradio.live','https://evil.test','https://a.gradio.live.evil.test']){let invalid=false;try{T.normalizeEndpoint(url);}catch{invalid=true;}check('Reject endpoint '+url,invalid);}
 const canvas=document.createElement('canvas');canvas.width=96;canvas.height=64;const ctx=canvas.getContext('2d');ctx.fillStyle='green';ctx.fillRect(0,0,96,64);
 const blob=await new Promise(r=>canvas.toBlob(r,'image/png'));
 const photo=i=>new File([blob],`photo-${i}.png`,{type:'image/png',lastModified:i});
 await T.addImages([photo(1),photo(2)]);check('Photo thumbnails',S.images.length===2&&$('image-list').children.length===2);
 await T.addImages([photo(1)]);check('Duplicate ignored',S.images.length===2);
 await T.addImages([new File(['not-image'],'bad.png',{type:'image/png'})]);check('Corrupt image rejected',S.images.length===2);
 await T.addImages([new File(['text'],'file.txt',{type:'text/plain'})]);check('Wrong type rejected',S.images.length===2);
 document.querySelector('.remove-image').click();check('Photo removal',S.images.length===1);
 await T.addImages([photo(1),...Array.from({length:12},(_,i)=>photo(i+3))]);check('Photo count limited to eight',S.images.length===8);
 $('guide-open').click();check('Guide opens', $('guide-dialog').open);$('guide-dialog').close();
 $('generate').click();check('Missing connection opens dialog',$('connect-dialog').open);$('connect-dialog').close();
 const sdk=await import('./vendor/gradio-client.js');check('Bundled Gradio SDK loads',typeof sdk.Client.connect==='function'&&typeof sdk.handle_file==='function');
 S.api=sdk;
 const originalFetch=window.fetch;const output='https://unit-test.gradio.live/gradio_api/file=/tmp/cloud.ply';
 $('endpoint').value='https://unit-test.gradio.live';let payload;
 S.client={submit:(name,input)=>{payload={name,input};return(async function*(){yield{type:'status',stage:'generating',progress_data:[{desc:'Mock GPU inference'}]};yield{type:'data',data:[{url:output},{image_count:8,elapsed_seconds:1.2}]};})();}};
 window.fetch=async(url,...args)=>String(url).startsWith('https://unit-test.gradio.live/')?new Response(plain):originalFetch(url,...args);
 $('generate').click();while(S.busy)await new Promise(r=>setTimeout(r,20));
 check('Reconstruction adapter submits images',payload.name==='/reconstruct'&&payload.input.images.length===8&&payload.input.quality==='fast');
 check('Returned PLY displayed',S.scene==='result'&&$('engine-label').textContent==='Pi3X · Colab GPU'&&$('result-image-count').textContent==='8장');
 check('No-confidence result disables filter',$('confidence').disabled);
 check('Busy controls recover',!$('generate').disabled&&$('processing').hidden);
 S.client={config:{api_prefix:'/gradio_api'},submit:()=> (async function*(){yield{type:'data',data:[{path:'/tmp/cloud.ply',url:'http://127.0.0.1:7860/gradio_api/file=/tmp/cloud.ply'},{image_count:8}]};})()};
 $('generate').click();while(S.busy)await new Promise(r=>setTimeout(r,20));
 check('Share tunnel internal file fallback',S.scene==='result'&&!$('task-status').classList.contains('error'));

 S.client={submit:()=> (async function*(){yield {type:'status',stage:'error',message:'GPU 메모리가 부족합니다.'};})()};
 $('generate').click();while(S.busy)await new Promise(r=>setTimeout(r,20));
 check('Inference failure keeps last result',S.scene==='result'&&$('task-status').classList.contains('error')&&!$('generate').disabled);
 window.fetch=originalFetch;S.client=null;$('endpoint').value='';
 for(const image of S.images)URL.revokeObjectURL(image.url);S.images=[];$('image-list').replaceChildren();$('image-count').textContent='0 / 8';$('task-status').textContent='사진을 추가하고 Colab을 연결해주세요.';$('task-status').classList.remove('error');$('toast').hidden=true;
 $('point-size').value=2;$('point-size').dispatchEvent(new Event('input'));T.showDemo();
 return results;
})()'''
results=c.js(script)
for x in results:print(('PASS' if x['pass'] else 'FAIL')+' '+x['name'])
c.call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1000,'deviceScaleFactor':1,'mobile':False});c.js('window.spaceTest.state.viewer.fit();new Promise(r=>setTimeout(r,300))');c.screenshot('/home/lee/vivecode/preview-desktop.png')
c.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
c.js('window.spaceTest.state.viewer.fit();new Promise(r=>setTimeout(r,300))')
mobile=c.js('({viewport:innerWidth,content:document.documentElement.scrollWidth,viewer:document.getElementById("viewer").getBoundingClientRect().width})')
assert mobile['viewport']==mobile['content'],mobile
print('PASS mobile horizontal overflow check',mobile)
r=c.call('Page.getLayoutMetrics');height=r['cssContentSize']['height'];r=c.call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':True,'clip':{'x':0,'y':0,'width':390,'height':height,'scale':1}})
import base64
open('/home/lee/vivecode/preview-mobile.png','wb').write(base64.b64decode(r['data']))
# Desktop with 200% equivalent responsive width. Ensure no clipping/overflow.
c.call('Emulation.setDeviceMetricsOverride',{'width':720,'height':500,'deviceScaleFactor':2,'mobile':False})
assert c.js('document.documentElement.scrollWidth<=innerWidth'),'overflow at 200% equivalent'
print('PASS 200% equivalent responsive width')
c.call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1000,'deviceScaleFactor':1,'mobile':False})
print('Tests:',len(results)+2)
