"""Independent Pi3X Mesh Space. Does not call or update the original Space."""
import spaces  # enable ZeroGPU emulation before importing torch
import hashlib
import json
import shutil
import tempfile
import time
import uuid
import zipfile
from pathlib import Path

import gradio as gr
import numpy as np
from PIL import Image
import models
from contracts import validate_cameras,validate_prompt
from geometry import (read_cloud,align_recovered,triangulate,unwrap_surface,surface_maps,
    render_frame,bake_camera,view_inputs,texture_image,export_scene,TEXTURE_SIZE,cpu_check)

ROOT = Path(tempfile.gettempdir())/'Pi3X_MESH_results'
ROOT.mkdir(exist_ok=True)
SCENES = {}
models.initialize()


def capabilities():
    return {'service':'pi3x-mesh','version':2,'texture_ready':models.PIPE is not None,
            'pose_recovery_ready':models.PI3 is not None,'errors':models.ERRORS,
            'model':models.DEPTH_REPO,'geometry_editing':False,
            'scope':'indoor_scene','method':'mesh_depth_shared_uv_inpainting','pbr_materials':False}


def pose_duration(paths,quality):
    return min(100,35+len(paths or [])*(5 if quality=='fast' else 7))


@spaces.GPU(duration=pose_duration)
def recover_poses(paths,quality):
    return models.recover(paths,quality)


@spaces.GPU(duration=45)
def paint_view(rendered,mask,depth,images,prompt,seed):
    return models.paint_view(rendered,mask,depth,images,prompt,seed)


def owner(request):
    if not request or not request.session_hash: raise gr.Error('같은 화면에서 다시 시도해주세요.')
    return request.session_hash


def purge():
    for key,scene in list(SCENES.items()):
        if scene['created'] < time.time()-6*3600:
            shutil.rmtree(scene['directory'],ignore_errors=True); SCENES.pop(key,None)


def prepare_scene(ply,images,poses,quality,request:gr.Request,progress=gr.Progress()):
    purge()
    directory = None
    try:
        session = owner(request)
        if not ply: raise ValueError('먼저 Pi3X PLY를 선택해주세요.')
        names = [Path(p).name for p in images or []]
        if len(set(names)) != len(names): raise ValueError('사진 파일 이름은 서로 달라야 해요.')
        progress(.05,desc='PLY와 원본 사진을 확인하고 있어요.')
        cloud,basis = read_cloud(Path(ply)); photos = models.load_images(images)
        alignment = {}
        if poses:
            if Path(poses).stat().st_size > 1024*1024: raise ValueError('포즈 JSON은 1 MB 이하로 선택해주세요.')
            document = json.loads(Path(poses).read_text())
            if isinstance(document,dict) and document.get('world_coordinate_system',basis) != basis:
                raise ValueError('PLY와 포즈의 world_coordinate_system을 맞춰주세요.')
            pose_source = 'uploaded'
        else:
            progress(.12,desc='새 Space에서 카메라 포즈를 복원하고 있어요.')
            document,predicted = recover_poses(images,quality)
            progress(.35,desc='카메라 포즈를 입력 PLY의 좌표에 맞추고 있어요.')
            document,alignment = align_recovered(predicted,cloud,document)
            pose_source = 'recovered_and_aligned'
        frames = validate_cameras(document,names)
        document['world_coordinate_system'] = basis
        progress(.5,desc='입력 점군의 표면을 연결해 메시를 만들고 있어요.')
        vertices,faces,colors = triangulate(cloud)
        key = uuid.uuid4().hex
        directory = ROOT/key; directory.mkdir()
        progress(.6,desc='실내 전체 메시의 UV를 만들고 있어요.')
        uv = unwrap_surface(vertices,faces)
        world,coverage,texture = surface_maps(vertices,faces,colors,uv)
        observed = np.zeros_like(coverage)
        for index,(frame,photo) in enumerate(zip(frames,photos)):
            progress(.65+.25*index/len(frames),desc=f'실내 카메라 {index+1}/{len(frames)}의 깊이와 원본 재질을 준비하고 있어요.')
            depth,coordinates = render_frame(vertices,faces,uv,frame)
            np.save(directory/f'depth-{index}.npy',depth)
            np.save(directory/f'view-uv-{index}.npy',coordinates)
            bake_camera(texture,observed,world,coverage,frame,depth,photo)
        ratio = float(observed.sum()/coverage.sum())
        if ratio < .1: raise ValueError('사진이 메시 표면과 맞지 않아요. 사진·포즈·PLY가 같은 장면인지 확인해주세요.')
        digest = hashlib.sha256(vertices.tobytes()+faces.tobytes()).hexdigest()
        metadata = {'scene_id':key,'vertex_count':len(vertices),'face_count':len(faces),
            'image_count':len(photos),'photographed_surface_ratio':round(ratio,3),
            'pose_source':pose_source,'geometry_sha256':digest,'geometry_preserved':True,
            'scope':'indoor_scene','texture_size':TEXTURE_SIZE,'method':'mesh_depth_shared_uv_inpainting',
            'coordinate_system':basis,'camera_coordinate_system':'OpenCV','display_coordinate_system':'Y_UP',**alignment,
            'limitation':'Observed indoor surfaces; no geometry editing, segmentation or full PBR generation.'}
        np.savez_compressed(directory/'mesh.npz',vertices=vertices,faces=faces,uv=uv,
            world=world,coverage=coverage,texture=texture)
        atlas = texture_image(texture,coverage)
        atlas.save(directory/'original-atlas.png')
        pose_file = directory/'cameras.json'
        pose_file.write_text(json.dumps(document,ensure_ascii=False,indent=2))
        output = directory/'original.glb'
        export_scene(output,vertices,faces,uv,atlas,metadata)
        bundle = directory/'posed-images.zip'
        with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(pose_file,'cameras.json'); archive.write(ply,'scene.ply')
            for original,name in zip(images,names): archive.write(original,'images/'+name)
        for index,photo in enumerate(photos): photo.save(directory/f'photo-{index}.png')
        SCENES[key] = {'owner':session,'created':time.time(),'directory':directory,
                       'metadata':metadata,'image_count':len(photos),'frames':frames}
        progress(1,desc='원본 메시와 포즈가 준비됐어요.')
        return str(output),key,str(pose_file),metadata,str(bundle)
    except (ValueError,OSError,KeyError,TypeError) as error:
        if directory: shutil.rmtree(directory,ignore_errors=True)
        raise gr.Error(str(error)) from None


def restyle_scene(scene_id,prompt,seed,request:gr.Request,progress=gr.Progress()):
    purge()
    try:
        scene = SCENES.get(scene_id)
        if not scene or scene['owner'] != owner(request): raise ValueError('원본 메시를 먼저 만들어주세요. 세션이 만료되면 다시 준비해야 해요.')
        prompt = validate_prompt(prompt)
        seed = int(seed)
        if not 0 <= seed <= 2147483647: raise ValueError('시드 값을 확인해주세요.')
        directory = scene['directory']
        if models.PIPE is None: raise ValueError('장면 텍스처 모델이 준비되지 않았어요. 서버 시작 로그를 확인해주세요.')
        tag = hashlib.sha256(json.dumps([prompt,seed,models.DEPTH_REVISION,models.BASE_REVISION]).encode()).hexdigest()[:20]
        cache = directory/f'style-{tag}.npz'
        output = directory/f'style-{tag}.glb'
        texture_file = directory/f'style-{tag}.png'
        info_file = directory/f'style-{tag}.json'
        if output.exists() and info_file.exists():
            return str(output),str(texture_file),json.loads(info_file.read_text())
        with np.load(directory/'mesh.npz',allow_pickle=False) as mesh:
            texture = mesh['texture'].copy(); coverage = mesh['coverage']; world = mesh['world']
            painted = np.zeros_like(coverage); next_view = 0
            if cache.exists():
                with np.load(cache,allow_pickle=False) as saved:
                    texture = saved['texture']; painted = saved['painted']; next_view = int(saved['next_view'])
            photos = []
            for i in range(scene['image_count']):
                with Image.open(directory/f'photo-{i}.png') as source: photos.append(source.convert('RGB'))
            for index,frame in enumerate(scene['frames']):
                if index < next_view: continue
                depth = np.load(directory/f'depth-{index}.npy',allow_pickle=False)
                coordinates = np.load(directory/f'view-uv-{index}.npy',allow_pickle=False)
                rendered,mask,control,count = view_inputs(texture,painted,depth,coordinates)
                progress(.1+.7*index/scene['image_count'],desc=f'실내 전체 장면 텍스처링 · 시점 {index+1}/{scene["image_count"]}')
                if count >= 24:
                    generated = paint_view(rendered,mask,control,photos,prompt,(seed+index)%2147483648)
                    bake_camera(texture,painted,world,coverage,frame,depth,generated)
                # Resume the same prompt after quota exhaustion, without repeating
                # completed camera views. Nothing is cached across visitors.
                temporary = directory/f'style-{tag}.tmp.npz'
                np.savez_compressed(temporary,texture=texture,painted=painted,next_view=index+1)
                temporary.replace(cache)
            if not painted.any(): raise ValueError('새 텍스처를 입힐 표면이 없어요. 포즈와 메시를 확인해주세요.')
            progress(.9,desc='공유 UV 텍스처를 고정된 장면 메시에 저장하고 있어요.')
            edited = texture_image(texture,coverage); edited.save(texture_file)
            metadata = {**scene['metadata'],'prompt':prompt,'seed':seed,'model':models.DEPTH_REPO,
                'model_revision':models.DEPTH_REVISION,'base_model':models.BASE_REPO,
                'base_revision':models.BASE_REVISION,'geometry_preserved':True,
                'styled_surface_ratio':round(float(painted.sum()/coverage.sum()),3),
                'material_channels':['base_color'],'pbr_materials':False}
            export_scene(output,mesh['vertices'],mesh['faces'],mesh['uv'],edited,metadata)
            info_file.write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
        progress(1,desc='새 분위기의 메시가 준비됐어요.')
        return str(output),str(texture_file),metadata
    except (ValueError,OSError,KeyError,TypeError) as error:
        raise gr.Error(str(error)) from None


with gr.Blocks(title='Pi3X Mesh Studio') as demo:
    gr.Markdown('# Pi3X Mesh Studio\n실내 전체 메시를 입력 카메라에서 렌더링하고, 하나의 공유 텍스처로 재질을 바꿉니다. 구조는 유지됩니다.')
    ply = gr.File(label='Pi3X PLY',file_types=['.ply'],type='filepath')
    images = gr.File(label='PLY 생성에 사용한 사진 2–8장',file_count='multiple',file_types=['image'],type='filepath')
    poses = gr.File(label='카메라 포즈 JSON (없으면 새 Space에서 복원)',file_types=['.json'],type='filepath')
    quality = gr.Radio(['fast','detail'],value='fast',label='기존 Pi3X 품질')
    prepare = gr.Button('원본 메시 만들기')
    original = gr.Model3D(label='원본 메시')
    scene_id = gr.Textbox(label='장면 ID',visible=False)
    cameras = gr.File(label='카메라 포즈')
    metadata = gr.JSON(label='장면 정보')
    bundle = gr.File(label='PLY·포즈·원본 이미지 묶음')
    prompt = gr.Textbox(label='실내 전체의 재질과 분위기 (영문 권장)',placeholder='A cozy living room with oak wood, beige linen, warm neutral walls')
    seed = gr.Number(value=0,precision=0,label='시드')
    gr.Markdown('형상과 가구 배치는 유지됩니다. 벽·의자별 영역 선택과 금속성·거칠기 생성은 아직 지원하지 않습니다. 같은 프롬프트를 다시 실행하면 완료한 시점부터 이어갑니다.')
    change = gr.Button('실내 전체 텍스처 바꾸기')
    styled = gr.Model3D(label='텍스처 메시')
    texture = gr.File(label='텍스처 이미지')
    changed_metadata = gr.JSON(label='편집 정보')
    prepare.click(prepare_scene,[ply,images,poses,quality],[original,scene_id,cameras,metadata,bundle],api_name='prepare_scene',concurrency_limit=1,concurrency_id='mesh')
    change.click(restyle_scene,[scene_id,prompt,seed],[styled,texture,changed_metadata],api_name='restyle_scene',concurrency_limit=1,concurrency_id='mesh')
    state = gr.JSON(visible=False)
    demo.load(capabilities,outputs=state,api_name='capabilities',queue=False,postprocess=False)
    check = gr.Button(visible=False)
    check.click(cpu_check,outputs=state,api_name='cpu_check',queue=False,postprocess=False)
demo.queue(max_size=4,default_concurrency_limit=1)
if __name__ == '__main__':
    demo.launch(server_name='0.0.0.0',server_port=7860,share=False,ssr_mode=False,
                show_error=True,max_file_size='40mb')
