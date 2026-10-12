import { normalizeEndpoint } from './gpu-backend.mjs';
import { uploadImages } from './gpu-upload.mjs';
import { watchGPUJob,jobProgress } from './gpu-job.mjs';
import { MeshViewer } from './mesh-viewer.js';

export function initMeshStudio({toast}) {
  const $=id=>document.getElementById(id);
  const state={source:null,sceneId:'',busy:false,client:null,endpoint:'',viewer:null,
    original:null,styled:null,downloadURLs:[],version:0,controller:null};
  const status=(text,error=false)=>{$('mesh-status').textContent=text;$('mesh-status').classList.toggle('error',error);};
  const controls=['mesh-prepare','mesh-style','mesh-ply','mesh-images','mesh-poses','mesh-prompt','mesh-quality','mesh-original','mesh-styled'];
  function busy(value) {
    state.busy=value;for(const id of controls)$(id).disabled=value;
    $('mesh-style').disabled=value||!state.sceneId;
    $('mesh-original').disabled=value||!state.original;$('mesh-styled').disabled=value||!state.styled;
    $('mesh-cancel').hidden=!value;
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
  async function connect() {
    if(state.client)return state.client;
    const response=await fetch(new URL('./space.config.json',import.meta.url),{cache:'no-store'});
    if(!response.ok)throw Error('새 Space 설정을 읽지 못했어요.');
    const config=await response.json();state.endpoint=normalizeEndpoint(config.meshEndpoint);
    const {Client}=await import('./vendor/gradio-client.js');
    const client=await Client.connect(state.endpoint,{events:['data','status']});
    const info=await client.view_api();
    if(!info.named_endpoints?.['/prepare_scene']||!info.named_endpoints?.['/restyle_scene']){client.close();throw Error('새 메시 Space가 아직 준비되지 않았어요.');}
    state.client=client;return client;
  }
  async function runJob(client,name,payload,version) {
    checkCurrent(version);
    const job=client.submit(name,payload);let output;
    let progress={label:'새 Space에 작업을 요청하고 있어요.',detail:''};
    const start=performance.now();
    const update=()=>status(`${progress.label}${progress.detail?' · '+progress.detail:''} · ${Math.floor((performance.now()-start)/1000)}초`);
    const timer=setInterval(update,1000);
    try {
      for await(const event of watchGPUJob(job,{signal:state.controller.signal})) {
        if(event.type==='data')output=event.data;
        if(event.type==='status'){
          if(event.stage==='error')throw Error(event.message||'메시 작업을 완료하지 못했어요.');
          progress=jobProgress(event,progress);update();
        }
      }
      checkCurrent(version);
      if(!Array.isArray(output))throw Error('결과를 받지 못했어요.');return output;
    }finally{clearInterval(timer);}
  }
  async function resultBlob(file) {
    if(!file?.path&&!file?.url)throw Error('결과 파일 주소가 없어요.');
    let url=file.url?new URL(file.url,state.endpoint):null;
    if(!url||url.protocol!=='https:'||url.origin!==state.endpoint){
      const prefix=state.client.config?.api_prefix||'/gradio_api';
      url=new URL(`${prefix}/file=${encodeURIComponent(file.path)}`,state.endpoint);
    }
    const response=await fetch(url);if(!response.ok)throw Error('결과 파일을 가져오지 못했어요.');
    return response.blob();
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
    const version=state.version;busy(true);state.controller=new AbortController();
    try {
      status('별도 메시 Space에 연결하고 있어요.');const client=await connect();checkCurrent(version);
      const caps=(await client.predict('/capabilities',{})).data?.[0];
      if(!poses&&!caps?.pose_recovery_ready)throw Error('새 Space의 포즈 복원 모델이 준비되지 않았어요.');
      status('PLY·원본 사진·포즈를 보내고 있어요.');
      const uploaded=await uploadImages(client,state.endpoint,[source.file,...source.images,...(poses?[poses]:[])]);
      checkCurrent(version);
      const output=await runJob(client,'/prepare_scene',{ply:uploaded[0],images:uploaded.slice(1,1+source.images.length),
        poses:poses?uploaded.at(-1):null,quality:source.quality},version);
      const original=await resultBlob(output[0]);const bundle=await resultBlob(output[4]);checkCurrent(version);
      state.original=original;state.styled=null;state.sceneId=output[1];
      download('mesh-bundle',bundle,'SPACE_posed-images.zip');await show('original');
      const coverage=Math.round((output[3]?.photographed_surface_ratio||0)*100);
      status(`실내 전체 메시 준비 완료 · 사진으로 덮인 표면 ${coverage}%. 원하는 재질과 분위기를 적어주세요.`);
    }catch(error){failed(error);}
    finally{state.controller=null;busy(false);}
  };
  $('mesh-style').onclick=async()=>{
    if(state.busy||!state.sceneId)return;
    const prompt=$('mesh-prompt').value.trim();if(prompt.length<2){toast('원하는 재질과 분위기를 적어주세요.');$('mesh-prompt').focus();return;}
    const version=state.version;busy(true);state.controller=new AbortController();
    try {
      const client=await connect();const caps=(await client.predict('/capabilities',{})).data?.[0];
      if(!caps?.texture_ready)throw Error('새 Space의 장면 텍스처 모델이 아직 준비되지 않았어요. 서버 시작 상태를 확인해주세요.');
      if(caps?.scope!=='indoor_scene')throw Error('새 Space의 장면 텍스처 버전으로 업데이트가 필요해요.');
      const output=await runJob(client,'/restyle_scene',{scene_id:state.sceneId,prompt,seed:0},version);
      const styled=await resultBlob(output[0]);const texture=await resultBlob(output[1]);checkCurrent(version);
      state.styled=styled;download('mesh-texture',texture,'SPACE_texture.png');await show('styled');
      const coverage=Math.round((output[2]?.styled_surface_ratio||0)*100);
      status(`실내 전체의 구조를 유지하고 텍스처를 바꿨어요 · 적용된 표면 ${coverage}%. 원본과 비교해보세요.`);
    }catch(error){failed(error);}
    finally{state.controller=null;busy(false);}
  };
  busy(false);
  return {setSource};
}
