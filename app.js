import { makeDemo } from './demo.js';
import { SpaceViewer } from './viewer.js';
import { GPUBackend, BackendUnavailable, normalizeEndpoint } from './gpu-backend.mjs';
import { jobProgress, watchGPUJob } from './gpu-job.mjs';
const $ = id => document.getElementById(id);
const state = { images: [], quality: 'fast', client: null, api: null, busy: false, viewer: null, scene: 'demo', backendStatus: 'connecting', activeController: null };
let toastTimer;
function toast(message) { $('toast').textContent=message; $('toast').hidden=false; clearTimeout(toastTimer); toastTimer=setTimeout(()=>$('toast').hidden=true,5500); }
function status(message,error=false) { $('task-status').textContent=message; $('task-status').classList.toggle('error',error); }
function setView(top=false) { state.viewer?.fit(top); for(const [id,active] of [['view-top',top],['view-perspective',!top]]) { $(id).classList.toggle('active',active); $(id).setAttribute('aria-pressed',String(active)); } $('auto-rotate').classList.remove('active'); $('auto-rotate').setAttribute('aria-pressed','false'); }
function showDemo() {
  if (state.busy || !state.viewer) return;
  state.viewer.setData(makeDemo()); state.scene='demo';
  $('scene-title').textContent='작은 거실, 큰 가능성';
  $('scene-tag').innerHTML='<span></span>INTERACTIVE DEMO';
  $('scene-caption-title').textContent='The quiet corner';
  $('scene-description').textContent='직접 회전하고, 가까이 들여다보세요.';
  $('result-image-count').textContent='예제 장면'; $('engine-label').textContent='예제 · 합성 데이터';
  $('confidence').disabled=false; $('confidence-hint').textContent='신뢰도가 낮은 점을 숨겨요.'; setView();
}
function renderImages() {
  $('image-count').textContent=`${state.images.length} / 8`;
  $('image-list').replaceChildren();
  state.images.forEach((entry,index)=>{
    const card=document.createElement('div'); card.className='image-thumb';
    const img=document.createElement('img');img.src=entry.url;img.alt=entry.file.name;
    const number=document.createElement('span');number.textContent=String(index+1).padStart(2,'0');
    const remove=document.createElement('button');remove.className='remove-image';remove.textContent='×';remove.title=entry.file.name+' 삭제';remove.setAttribute('aria-label',entry.file.name+' 삭제');remove.disabled=state.busy;
    remove.onclick=()=>{URL.revokeObjectURL(entry.url);state.images.splice(index,1);renderImages();};
    card.append(img,number,remove);$('image-list').append(card);
  });
  if(!state.busy)status(state.images.length<2 ? '같은 공간의 사진을 2장 이상 추가해주세요.' : state.backendStatus === 'ready' ? '준비됐어요. 나만의 공간을 만들어보세요.' : state.backendStatus === 'connecting' ? '사진이 준비됐어요. 서버에 연결하고 있어요.' : '사진이 준비됐어요. 서버 준비 후 다시 시도해주세요.');
}
async function addImages(files) {
  if(state.busy)return;
  const errors=[];
  for(const file of files) {
    if(state.images.length>=8){errors.push('사진은 최대 8장까지 추가할 수 있어요.');break;}
    if(!['image/jpeg','image/png','image/webp'].includes(file.type)){errors.push('JPG, PNG, WEBP 사진을 선택해주세요.');continue;}
    if(file.size>15*1024*1024){errors.push('장당 15 MB 이하의 사진을 선택해주세요.');continue;}
    if(state.images.some(x=>x.file.name===file.name&&x.file.size===file.size&&x.file.lastModified===file.lastModified))continue;
    const url=URL.createObjectURL(file);
    try { const img=new Image();img.src=url;await img.decode();if(img.width<28||img.height<28)throw Error(); }
    catch { URL.revokeObjectURL(url);errors.push('읽을 수 없는 사진이 있어요. 다른 파일을 선택해주세요.');continue; }
    if(state.busy||state.images.length>=8){URL.revokeObjectURL(url);continue;}
    state.images.push({file,url});
  }
  renderImages();if(errors.length)toast([...new Set(errors)].join(' '));
}
$('dropzone').onclick=()=>$('image-input').click();
let autoGenerateTimer;
function scheduleGeneration(previousCount) {
  if(state.busy || state.images.length<2 || state.images.length===previousCount)return;
  clearTimeout(autoGenerateTimer);
  autoGenerateTimer=setTimeout(()=>{if(!state.busy&&state.images.length>=2)$('generate').click();},400);
}
$('image-input').onchange=async e=>{const before=state.images.length;await addImages(e.target.files);e.target.value='';scheduleGeneration(before);};
for(const event of ['dragenter','dragover'])$('dropzone').addEventListener(event,e=>{e.preventDefault();if(!state.busy)$('dropzone').classList.add('dragover');});
for(const event of ['dragleave','drop'])$('dropzone').addEventListener(event,e=>{e.preventDefault();$('dropzone').classList.remove('dragover');if(event==='drop'){const before=state.images.length;addImages(e.dataTransfer.files).then(()=>scheduleGeneration(before));}});
document.querySelectorAll('[data-quality]').forEach(button=>button.onclick=()=>{
  if(state.busy)return;state.quality=button.dataset.quality;
  document.querySelectorAll('[data-quality]').forEach(b=>{b.classList.toggle('active',b===button);b.setAttribute('aria-pressed',String(b===button));});
  $('quality-note').textContent=state.quality==='fast'?'처음에는 사진 3–4장으로 시작해보세요.':'더 선명한 공간을 만들어요. 처리 시간이 조금 더 필요해요.';
});
$('guide-open').onclick=()=>$('guide-dialog').showModal();
const guide = $('guide-dialog');
guide.addEventListener('click',e=>{if(e.target!==guide)return;const r=guide.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)guide.close();});
const backend = new GPUBackend({onStatus: phase => {
  state.backendStatus = phase;
  $('connection-dot').classList.toggle('connected', phase === 'ready');
  $('connection-dot').classList.toggle('connecting', phase === 'connecting');
  $('connection-label').textContent = phase === 'ready' ? '서버 연결됨' : phase === 'connecting' ? '서버 연결 중' : '서버 준비 중';
  if (!state.busy) renderImages();
}});
function setBusy(busy) {
  state.busy=busy;$('processing').hidden=!busy;
  for(const id of ['generate','dropzone','demo-button','import-button','export'])$(id).disabled=busy;
  document.querySelectorAll('[data-quality],.remove-image').forEach(b=>b.disabled=busy);
  $('generate').querySelector('span').textContent=busy?'공간을 만드는 중…':'3D 공간 만들기';
  $('cancel-generation').disabled=!busy || !state.activeController;
}
$('cancel-generation').onclick=()=>state.activeController?.abort();
$('generate').onclick=async()=>{
  clearTimeout(autoGenerateTimer);
  if(state.busy)return;
  if(!state.viewer){toast('3D 뷰어를 사용할 수 없어요. WebGL을 지원하는 브라우저에서 열어주세요.');return;}
  if(state.images.length<2){toast('같은 공간의 사진을 2장 이상 추가해주세요.');$('dropzone').focus();return;}
  setBusy(true);status('사진을 처리할 준비를 하고 있어요.');
  $('processing-label').textContent='공간 만들기를 준비하는 중';$('processing-detail').textContent='잠시만 기다려주세요.';
  let elapsedTimer;
  try {
    const connection = await backend.ensureReady();
    state.client = connection.client; state.api = connection.api;
    status('사진을 전송하고 있어요.');
    $('processing-label').textContent='사진을 보내는 중';$('processing-detail').textContent='업로드 후 사진 속 공간을 이어줍니다.';
    const job=state.client.submit('/reconstruct',{images:state.images.map(x=>state.api.handle_file(x.file)),quality:state.quality});
    state.activeController=new AbortController();$('cancel-generation').disabled=false;
    const startedAt=performance.now();
    let progress={phase:'upload',label:'사진을 보내는 중',detail:'업로드 후 사진 속 공간을 이어줍니다.'};
    const updateProgress=()=>{
      const seconds=Math.floor((performance.now()-startedAt)/1000);
      $('processing-label').textContent=progress.label;
      $('processing-detail').textContent=progress.detail+` · ${seconds}초 경과`;
    };
    elapsedTimer=setInterval(updateProgress,1000);
    let output;
    for await(const message of watchGPUJob(job,{signal:state.activeController.signal})) {
      if(message.type==='data')output=message.data;
      if(message.type==='status') {
        if(message.stage==='error')throw Error(message.message||'공간을 만들지 못했어요. 다시 시도해주세요.');
        progress=jobProgress(message,progress);updateProgress();
      }
    }
    clearInterval(elapsedTimer);
    state.activeController=null;$('cancel-generation').disabled=true;
    const file=output?.[0];
    if(!file?.url&&!file?.path)throw Error('결과를 받지 못했어요. 다시 시도해주세요.');
    $('processing-label').textContent='나만의 공간을 열고 있어요';
    const endpoint=connection.endpoint;
    let url=file.url?new URL(file.url,endpoint):null;
    // Gradio behind a share tunnel can return an internal file URL. Use the
    // returned server path through the connected public API in that case.
    if(!url||url.protocol!=='https:'||url.origin!==endpoint) {
      if(typeof file.path!=='string'||!file.path)throw Error('결과 파일 주소를 확인할 수 없습니다.');
      const prefix=state.client.config?.api_prefix||'/gradio_api';
      url=new URL(`${prefix}/file=${encodeURIComponent(file.path)}`,endpoint);
    }
    const response=await fetch(url.href);if(!response.ok)throw Error('결과를 가져오지 못했어요. 다시 시도해주세요.');
    const result=state.viewer.parsePLY(await response.arrayBuffer());state.scene='result';
    const meta=output[1]||{};
    $('scene-title').textContent='나의 첫 번째 공간';$('scene-tag').innerHTML='<span></span>YOUR RECONSTRUCTION';
    $('scene-caption-title').textContent='My reconstructed space';$('scene-description').textContent='사진 속 공간이 새로운 시점으로 펼쳐집니다.';
    $('result-image-count').textContent=`${meta.image_count||state.images.length}장`;$('engine-label').textContent='Pi3X';
    $('confidence').disabled=!result.hasConfidence;$('confidence-hint').textContent=result.hasConfidence?'신뢰도가 낮은 점을 숨겨요.':'이 파일에는 신뢰도 정보가 없어요.';
    setView();status(`완성됐어요${meta.elapsed_seconds?` · ${meta.elapsed_seconds}초`:''}. 회전하며 공간을 살펴보세요.`);toast('나만의 3D 공간이 완성됐어요.');
  }catch(e){
    const message=e instanceof BackendUnavailable || ['AbortError','TimeoutError'].includes(e.name) ? e.message : /quota|daily.*GPU|GPU.*budget/i.test(e.message||'') ? '무료 GPU 사용량이 부족해요. 사용량이 초기화된 뒤 다시 시도해주세요.' : '공간을 만들지 못했어요. 사진 수를 줄이거나 다른 사진으로 다시 시도해주세요.';
    status(message,true);toast(message);state.client=null;backend.invalidate();
    console.warn('Reconstruction:',e.message);
  }
  finally{clearInterval(elapsedTimer);state.activeController=null;setBusy(false);}
};
$('demo-button').onclick=()=>{showDemo();toast('합성 예제 장면이에요. 드래그해 공간을 탐색해보세요.');};
$('view-top').onclick=()=>setView(true);$('view-perspective').onclick=()=>setView();$('reset-view').onclick=()=>setView();
$('auto-rotate').onclick=()=>{if(!state.viewer)return;const active=!state.viewer.controls.autoRotate;state.viewer.controls.autoRotate=active;$('auto-rotate').classList.toggle('active',active);$('auto-rotate').setAttribute('aria-pressed',String(active));};
$('canvas-mount').addEventListener('pointerdown',()=>{$('auto-rotate').classList.remove('active');$('auto-rotate').setAttribute('aria-pressed','false');});
$('fullscreen').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await $('viewer').requestFullscreen();}catch{toast('이 브라우저에서는 전체 화면을 사용할 수 없어요.');}};
$('point-size').oninput=e=>{const n=Number(e.target.value);state.viewer?.setSize(n);$('point-size-value').value=n.toFixed(1);};
$('confidence').oninput=e=>{const n=Number(e.target.value);state.viewer?.setThreshold(n/100);$('confidence-value').value=n+'%';};
document.querySelectorAll('[data-color]').forEach(button=>button.onclick=()=>{state.viewer?.setColor(button.dataset.color);document.querySelectorAll('[data-color]').forEach(b=>{b.classList.toggle('active',b===button);b.setAttribute('aria-pressed',String(b===button));});});
$('import-button').onclick=()=>$('ply-input').click();
$('ply-input').onchange=async e=>{
  const file=e.target.files[0];e.target.value='';if(!file||state.busy)return;
  if(!state.viewer){toast('WebGL을 지원하는 브라우저에서 열어주세요.');return;}
  try {
    if(file.size>100*1024*1024)throw Error('100 MB 이하의 PLY 파일을 선택해주세요.');
    const result=state.viewer.parsePLY(await file.arrayBuffer());state.scene='import';
    $('scene-title').textContent=file.name;$('scene-tag').innerHTML='<span></span>IMPORTED SPACE';$('scene-caption-title').textContent='Your saved space';$('scene-description').textContent='저장한 결과를 다시 탐색해보세요.';
    $('result-image-count').textContent='—';$('engine-label').textContent='PLY 불러오기';$('confidence').disabled=!result.hasConfidence;
    $('confidence-hint').textContent=result.hasConfidence?'신뢰도가 낮은 점을 숨겨요.':'이 파일에는 신뢰도 정보가 없어요.';setView();toast('저장한 3D 공간을 불러왔어요.');
  }catch(error){toast(error.message||'PLY를 읽지 못했어요. 파일을 확인해주세요.');}
};
$('export').onclick=()=>{
  if(!state.viewer||state.busy)return;
  try { const blob=state.viewer.exportPLY(),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=state.scene==='demo'?'SPACE_synthetic_demo.ply':'SPACE_reconstruction.ply';a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);toast('현재 노이즈 설정을 적용한 PLY를 저장했어요.'); }
  catch(e){toast(e.message);}
};
try {
  state.viewer=new SpaceViewer($('canvas-mount'),count=>$('point-count').textContent=new Intl.NumberFormat('ko-KR').format(count));showDemo();
  $('canvas-mount').querySelector('canvas').setAttribute('aria-label','드래그로 회전하고 확대할 수 있는 3D 점 구름');
  document.documentElement.dataset.ready='true';
}catch(e){$('viewer-error').hidden=false;$('viewer-error').textContent='3D 화면을 시작하지 못했어요. Chrome 또는 Edge에서 하드웨어 가속을 켠 뒤 다시 열어주세요.';console.error(e);}
// Read-only browser test access; exposed only when explicitly requested.
if(new URLSearchParams(location.search).has('test'))window.spaceTest={state,backend,addImages,normalizeEndpoint,showDemo};

// The owner can test a running session via the Colab return link. Visitors
// normally use the endpoint in the published configuration automatically.
const colabEndpoint = new URLSearchParams(location.search).get('colab');
if(colabEndpoint) {
  const cleanUrl=new URL(location.href);cleanUrl.searchParams.delete('colab');
  history.replaceState(null,'',cleanUrl);
  try { backend.useSessionEndpoint(colabEndpoint); } catch(error) { console.warn(error.message); }
}
backend.ensureReady().then(connection=>{state.client=connection.client;state.api=connection.api;})
  .catch(()=>{if(!state.busy)status('지금은 서버를 준비하고 있어요. 예제 공간을 먼저 둘러보세요.');});
