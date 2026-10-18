// Mesh work includes CPU meshing as well as GPU work; keep its labels separate
// from the Pi3X point-cloud job and never invent a percentage from elapsed time.
export function meshJobProgress(message, previous = {}) {
  const items=(message.progress_data||[]).filter(item=>item.desc);
  const item=items.at(-1);
  if(item) {
    let fraction=Number.isFinite(item.progress)?item.progress:null;
    if(fraction===null&&item.length>0&&Number.isFinite(item.index))fraction=item.index/item.length;
    return {started:true,label:item.desc,detail:'서버에서 장면을 처리하고 있어요.',
      percent:fraction!==null&&fraction>=0&&fraction<=1?Math.round(fraction*100):null};
  }
  if(previous.started)return previous;
  if(message.original_msg==='process_starts'||['generating','streaming','complete'].includes(message.stage))
    return {started:true,label:'장면 처리를 시작했어요',detail:'서버의 다음 진행 안내를 기다리고 있어요.',percent:null};
  return {started:false,label:'작업 순서를 기다리고 있어요',percent:null,
    detail:message.position!=null?`이 서버의 대기 순서 ${message.position+1}번째`:'공유 서버에 요청을 전달했어요.'};
}

export function elapsedLabel(milliseconds) {
  const seconds=Math.max(0,Math.floor(milliseconds/1000));
  return seconds<60?`${seconds}초`:`${Math.floor(seconds/60)}분 ${seconds%60}초`;
}

export function abortError() {
  const error=Error('작업 대기를 취소했어요. 입력 사진과 이전 결과는 유지됩니다.');
  error.name='AbortError';return error;
}

// Unlike predict/upload/connect promises, this wait is bounded and abortable.
// A connection that resolves after cancellation is closed instead of reused.
export async function waitForMesh(operation,{signal,timeout=60000,message='서버 응답이 늦어 대기를 끝냈어요. 다시 시도해주세요.',onLateValue}={}) {
  if(signal?.aborted)throw abortError();
  let timer,abort,stopped=false;
  const work=Promise.resolve().then(operation);
  work.then(value=>{if(stopped){try{onLateValue?.(value);}catch{}}},()=>{});
  const stop=new Promise((_,reject)=>{
    abort=()=>{stopped=true;reject(abortError());};
    signal?.addEventListener('abort',abort,{once:true});
    timer=setTimeout(()=>{stopped=true;const error=Error(message);error.name='TimeoutError';reject(error);},timeout);
  });
  try{return await Promise.race([work,stop]);}
  finally{clearTimeout(timer);signal?.removeEventListener('abort',abort);}
}

export function meshResultURL(file,endpoint,apiPrefix='/gradio_api') {
  if(!file?.path&&!file?.url)throw Error('결과 파일 주소가 없어요.');
  const url=file.url?new URL(file.url,endpoint):null;
  if(url?.protocol==='https:'&&url.origin===endpoint)return url.href;
  if(!file.path)throw Error('결과 파일 경로를 확인할 수 없어요.');
  return new URL(`${apiPrefix}/file=${encodeURIComponent(file.path)}`,endpoint).href;
}
