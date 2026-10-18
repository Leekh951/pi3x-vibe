import { normalizeEndpoint } from './gpu-backend.mjs';
import { uploadImages } from './gpu-upload.mjs';
import { watchGPUJob } from './gpu-job.mjs';
import { meshJobProgress,elapsedLabel,waitForMesh,meshResultURL,abortError } from './mesh-progress.mjs';
import { MeshViewer } from './mesh-viewer.js';

export function initMeshStudio({toast}) {
  const $=id=>document.getElementById(id);
  const state={source:null,sceneId:'',busy:false,client:null,endpoint:'',viewer:null,
    original:null,styled:null,downloadURLs:[],version:0,controller:null,task:null,timer:null};
  const status=(text,error=false)=>{$('mesh-status').textContent=text;$('mesh-status').classList.toggle('error',error);};
  const controls=['mesh-prepare','mesh-style','mesh-ply','mesh-images','mesh-poses','mesh-prompt','mesh-quality','mesh-original','mesh-styled'];
  function busy(value) {
    state.busy=value;for(const id of controls)$(id).disabled=value;
    $('mesh-style').disabled=value||!state.sceneId;
    $('mesh-original').disabled=value||!state.original;$('mesh-styled').disabled=value||!state.styled;
    $('mesh-cancel').hidden=!value;
    $('mesh-processing').hidden=!value;
    $('mesh-progress-steps').hidden=!value;
    $('mesh-progress-timing').hidden=!value;
    $('mesh-viewer').setAttribute('aria-busy',String(value));
  }
  function paintTask() {
    const task=state.task;if(!task)return;
    const now=performance.now();
    $('mesh-processing-title').textContent=task.label;
    $('mesh-processing-detail').textContent=task.detail;
    $('mesh-progress-timing').textContent=`전체 ${elapsedLabel(now-task.start)} · 현재 단계 ${elapsedLabel(now-task.phaseStart)}`;
    $('mesh-processing-time').textContent=`전체 ${elapsedLabel(now-task.start)}`;
    $('mesh-processing-update').textContent=task.responseAt!==null?`마지막 서버 응답 ${elapsedLabel(now-task.responseAt)} 전`:'서버에 연결하고 있어요.';
    $('mesh-processing-hint').textContent=now-task.phaseStart>45000?
      '사진 수와 공간의 복잡도에 따라 시간이 걸릴 수 있어요. 입력을 유지한 채 대기를 취소할 수 있습니다.':'';
    const bar=$('mesh-progress-bar');const percent=task.percent;
    bar.classList.toggle('indeterminate',percent===null);
    if(percent===null)bar.removeAttribute('aria-valuenow');else bar.setAttribute('aria-valuenow',String(percent));
    bar.firstElementChild.style.width=percent===null?'30%':`${percent}%`;
    $('mesh-progress-caption').textContent=percent===null?'단계별 진행 상황을 기다리고 있어요.':`서버가 보고한 처리 단계 ${percent}%`;
    [...$('mesh-progress-steps').children].forEach((step,index)=>{
      step.textContent=task.steps[index];step.classList.toggle('active',index===task.step);
      step.classList.toggle('done',index<task.step);
      if(index===task.step)step.setAttribute('aria-current','step');else step.removeAttribute('aria-current');
    });
  }
  function phase(step,label,detail='',percent=null) {
    if(!state.task)return;
    if(state.task.step!==step||state.task.label!==label)state.task.phaseStart=performance.now();
    Object.assign(state.task,{step,label,detail,percent});status(label+(detail?' · '+detail:''));paintTask();
  }
  function startTask(kind) {
    state.controller=new AbortController();
    const now=performance.now();
    state.task={start:now,phaseStart:now,responseAt:null,step:0,percent:null,
      label:'메시 서버에 연결하고 있어요',detail:'처음 연결할 때 서버 준비에 시간이 걸릴 수 있어요.',
      steps:kind==='prepare'?['서버 연결','파일 전송','장면 생성','3D 화면 표시']:['서버 연결','모델 확인','텍스처 생성','3D 화면 표시']};
    busy(true);status(state.task.label+' · '+state.task.detail);paintTask();state.timer=setInterval(paintTask,1000);
    $('mesh-progress-panel').scrollIntoView({behavior:'smooth',block:'start'});
  }
  function finishTask() {
    clearInterval(state.timer);state.timer=null;
    state.controller?.abort();state.controller=null;state.task=null;busy(false);
  }
  function sourceLabel() {
    const source=state.source;
    $('mesh-source').textContent=source?`${source.file.name} · 원본 사진 ${source.images.length}장`:'위에서 Pi3X 결과를 만들거나 PLY와 원본 사진을 선택해주세요.';
  }
  function resetPrepared() {
    state.version++;state.controller?.abort();state.sceneId='';state.original=null;state.styled=null;
    for(const url of state.downloadURLs)URL.revokeObjectURL(url);state.downloadURLs=[];
    for(const id of ['mesh-download','mesh-bundle','mesh-texture']){$(id).hidden=true;$(id).removeAttribute('href');}
    $('mesh-empty').hidden=false;$('mesh-mount').hidden=true;
    $('mesh-original').classList.remove('active');$('mesh-styled').classList.remove('active');
    $('mesh-style').disabled=true;$('mesh-original').disabled=true;$('mesh-styled').disabled=true;
  }
  function setSource(file,images,quality='fast') {
    resetPrepared();state.source={file,images:[...images],quality};
    $('mesh-quality').value=quality;$('mesh-ply').value='';$('mesh-images').value='';$('mesh-poses').value='';sourceLabel();
    status('원본 메시를 먼저 만든 뒤 원하는 재질과 분위기를 적어주세요.');
  }
  const checkCurrent=version=>{if(version!==state.version)throw Error('입력이 바뀌었어요. 새 입력으로 원본 메시를 만들어주세요.');};
  async function connect(signal) {
    if(state.client)return state.client;
    const config=await waitForMesh(async()=>{
      const response=await fetch(new URL('./space.config.json',import.meta.url),{cache:'no-store',signal});
      if(!response.ok)throw Error('새 Space 설정을 읽지 못했어요.');
      return response.json();
    },{signal,timeout:15000});state.endpoint=normalizeEndpoint(config.meshEndpoint);
    const {Client}=await waitForMesh(()=>import('./vendor/gradio-client.js'),{signal,timeout:20000});
    const client=await waitForMesh(()=>Client.connect(state.endpoint,{events:['data','status']}),{
      signal,timeout:90000,message:'메시 서버 연결이 90초 동안 완료되지 않았어요. 잠시 후 다시 시도해주세요.',onLateValue:value=>value.close()});
    try {
      const info=await waitForMesh(()=>client.view_api(),{signal,timeout:20000});
      if(!info.named_endpoints?.['/prepare_scene']||!info.named_endpoints?.['/restyle_scene'])throw Error('새 메시 Space가 아직 준비되지 않았어요.');
      if(signal.aborted)throw abortError();
      state.client=client;return client;
    }catch(error){client.close();throw error;}
  }
  async function capabilities(client,signal) {
    const result=await waitForMesh(()=>client.predict('/capabilities',{}),{
      signal,timeout:20000,message:'메시 서버의 준비 상태를 확인하지 못했어요. 잠시 후 다시 시도해주세요.'});
    if(state.task)state.task.responseAt=performance.now();
    return result.data?.[0];
  }
  async function runJob(client,name,payload,version) {
    checkCurrent(version);
    const job=client.submit(name,payload);let output;
    let progress={label:'새 Space에 작업을 요청하고 있어요.',detail:''};
    phase(2,'서버에서 요청을 받고 있어요','장면 처리 단계가 시작되면 여기에 표시됩니다.');
    for await(const event of watchGPUJob(job,{signal:state.controller.signal})) {
        if(event.type==='data')output=event.data;
        if(event.type==='status'){
          if(event.stage==='error')throw Error(event.message||'메시 작업을 완료하지 못했어요.');
          state.task.responseAt=performance.now();
          progress=meshJobProgress(event,progress);phase(2,progress.label,progress.detail,progress.percent);
        }
    }
    checkCurrent(version);
    if(!Array.isArray(output))throw Error('결과를 받지 못했어요.');return output;
  }
  async function resultBlob(file) {
    const signal=state.controller.signal;
    return waitForMesh(async()=>{
      const response=await fetch(meshResultURL(file,state.endpoint,state.client.config?.api_prefix),{signal});
      if(!response.ok)throw Error('결과 파일을 가져오지 못했어요.');
      const total=Number(response.headers.get('content-length'))||0;
      if(!response.body)return response.blob();
      const reader=response.body.getReader(),chunks=[];let received=0;
      while(true){
        const {done,value}=await reader.read();if(done)break;
        if(signal.aborted)throw abortError();
        chunks.push(value);received+=value.byteLength;
        if(state.task){state.task.responseAt=performance.now();phase(3,'완성된 메시를 받고 있어요',`${(received/1048576).toFixed(1)} MB 수신`,total>0?Math.min(100,Math.round(received/total*100)):null);}
      }
      return new Blob(chunks,{type:response.headers.get('content-type')||'model/gltf-binary'});
    },{signal,timeout:90000,message:'메시 파일 전송이 90초 동안 끝나지 않았어요. 네트워크 상태를 확인해주세요.'});
  }
  function remoteDownload(id,file,name) {
    $(id).href=meshResultURL(file,state.endpoint,state.client.config?.api_prefix);
    $(id).download=name;$(id).target='_blank';$(id).rel='noopener';$(id).hidden=false;
  }
  function download(id,blob,name) {
    const url=URL.createObjectURL(blob);state.downloadURLs.push(url);
    $(id).href=url;$(id).download=name;$(id).hidden=false;
  }
  async function show(kind) {
    const blob=state[kind];if(!blob)return;
    if(!state.viewer)state.viewer=new MeshViewer($('mesh-mount'));
    $('mesh-mount').hidden=false;state.viewer.resize();await state.viewer.show(await blob.arrayBuffer());
    $('mesh-empty').hidden=true;
    $('mesh-original').classList.toggle('active',kind==='original');$('mesh-styled').classList.toggle('active',kind==='styled');
    download('mesh-download',blob,kind==='original'?'SPACE_original.glb':'SPACE_styled.glb');
  }
  function failed(error) {
    if(error.name==='TimeoutError'){state.client?.close();state.client=null;}
    const message=/quota|budget|daily.*GPU/i.test(error.message)?'새 Space의 GPU 사용량이 부족해요. 로그인해서 이용하거나 초기화 후 다시 시도해주세요.':error.message||'새 Space에 연결하지 못했어요.';
    status(message,true);toast(message);
  }
  $('mesh-ply').onchange=e=>{
    const file=e.target.files[0];if(!file)return;resetPrepared();
    state.source={file,images:state.source?.images||[],quality:$('mesh-quality').value};sourceLabel();
  };
  $('mesh-images').onchange=e=>{
    if(!state.source){toast('PLY를 먼저 선택해주세요.');e.target.value='';return;}
    resetPrepared();state.source.images=[...e.target.files];sourceLabel();
  };
  $('mesh-poses').onchange=()=>resetPrepared();
  $('mesh-quality').onchange=()=>{resetPrepared();if(state.source)state.source.quality=$('mesh-quality').value;};
  $('mesh-cancel').onclick=()=>state.controller?.abort();
  $('mesh-original').onclick=()=>show('original').catch(failed);
  $('mesh-styled').onclick=()=>show('styled').catch(failed);
  $('mesh-prepare').onclick=async()=>{
    if(state.busy)return;
    const source=state.source;
    if(!source||source.images.length<2||source.images.length>8){toast('Pi3X PLY와 생성에 사용한 원본 사진 2–8장이 필요해요.');return;}
    const poses=$('mesh-poses').files[0]||null;
    if(source.file.size>40*1024*1024||source.images.some(f=>f.size>15*1024*1024)||poses?.size>1024*1024){toast('PLY 40 MB, 사진 장당 15 MB, 포즈 JSON 1 MB 이하로 선택해주세요.');return;}
    const version=state.version;startTask('prepare');const signal=state.controller.signal;
    try {
      const client=await connect(signal);checkCurrent(version);
      phase(0,'메시 서버의 준비 상태를 확인하고 있어요');
      const caps=await capabilities(client,signal);
      if(!poses&&!caps?.pose_recovery_ready)throw Error('새 Space의 포즈 복원 모델이 준비되지 않았어요.');
      phase(1,'PLY와 원본 사진을 보내고 있어요',`사진 ${source.images.length}장${poses?' · 저장된 카메라 포즈 사용':' · 전송 후 카메라 포즈 복원'}`);
      const uploaded=await waitForMesh(()=>uploadImages(client,state.endpoint,[source.file,...source.images,...(poses?[poses]:[])]),{
        signal,timeout:120000,message:'파일 전송이 2분 동안 완료되지 않았어요. 네트워크 상태를 확인하고 다시 시도해주세요.'});
      checkCurrent(version);
      const output=await runJob(client,'/prepare_scene',{ply:uploaded[0],images:uploaded.slice(1,1+source.images.length),
        poses:poses?uploaded.at(-1):null,quality:source.quality},version);
      phase(3,'완성된 메시를 받고 있어요','원본 사진 묶음은 저장할 때만 다운로드합니다.');
      const original=await resultBlob(output[0]);checkCurrent(version);
      state.original=original;state.styled=null;state.sceneId=output[1];
      remoteDownload('mesh-bundle',output[4],'SPACE_posed-images.zip');
      phase(3,'3D 화면을 열고 있어요','메시를 화면에 준비하고 있어요.');
      await show('original');checkCurrent(version);
      const coverage=Math.round((output[3]?.photographed_surface_ratio||0)*100);
      status(`실내 전체 메시 준비 완료 · 사진으로 덮인 표면 ${coverage}%. 원하는 재질과 분위기를 적어주세요.`);
    }catch(error){if(version===state.version)failed(error);}
    finally{finishTask();}
  };
  $('mesh-style').onclick=async()=>{
    if(state.busy||!state.sceneId)return;
    const prompt=$('mesh-prompt').value.trim();if(prompt.length<2){toast('원하는 재질과 분위기를 적어주세요.');$('mesh-prompt').focus();return;}
    const version=state.version;startTask('style');const signal=state.controller.signal;
    try {
      const client=await connect(signal);checkCurrent(version);
      phase(1,'텍스처 모델의 준비 상태를 확인하고 있어요');
      const caps=await capabilities(client,signal);
      if(!caps?.texture_ready)throw Error('새 Space의 장면 텍스처 모델이 아직 준비되지 않았어요. 서버 시작 상태를 확인해주세요.');
      if(caps?.scope!=='indoor_scene')throw Error('새 Space의 장면 텍스처 버전으로 업데이트가 필요해요.');
      const output=await runJob(client,'/restyle_scene',{scene_id:state.sceneId,prompt,seed:0},version);
      phase(3,'새 텍스처가 적용된 메시를 받고 있어요');
      const styled=await resultBlob(output[0]);checkCurrent(version);
      state.styled=styled;remoteDownload('mesh-texture',output[1],'SPACE_texture.png');
      phase(3,'3D 화면을 열고 있어요');await show('styled');checkCurrent(version);
      const coverage=Math.round((output[2]?.styled_surface_ratio||0)*100);
      status(`실내 전체의 구조를 유지하고 텍스처를 바꿨어요 · 적용된 표면 ${coverage}%. 원본과 비교해보세요.`);
    }catch(error){if(version===state.version)failed(error);}
    finally{finishTask();}
  };
  busy(false);
  return {setSource};
}
