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
from geometry import read_cloud,align_recovered,triangulate,camera_uv,build_atlas,export_scene

ROOT = Path(tempfile.gettempdir())/'Pi3X_MESH_results'
ROOT.mkdir(exist_ok=True)
SCENES = {}
models.initialize()


def capabilities():
    return {'service':'pi3x-mesh','version':1,'texture_ready':models.PIPE is not None,
            'pose_recovery_ready':models.PI3 is not None,'errors':models.ERRORS,
            'model':models.FLUX_REPO,'geometry_editing':False}


def pose_duration(paths,quality):
    return min(100,35+len(paths or [])*(5 if quality=='fast' else 7))


@spaces.GPU(duration=pose_duration)
def recover_poses(paths,quality):
    return models.recover(paths,quality)


@spaces.GPU(duration=60)
def edit_images(atlas,images,prompt,seed):
    return models.restyle(atlas,images,prompt,seed)


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
        cloud = read_cloud(Path(ply)); photos = models.load_images(images)
        alignment = {}
        if poses:
            if Path(poses).stat().st_size > 1024*1024: raise ValueError('포즈 JSON은 1 MB 이하로 선택해주세요.')
            document = json.loads(Path(poses).read_text())
            pose_source = 'uploaded'
        else:
            progress(.12,desc='새 Space에서 카메라 포즈를 복원하고 있어요.')
            document,predicted = recover_poses(images,quality)
            progress(.35,desc='카메라 포즈를 입력 PLY의 좌표에 맞추고 있어요.')
            document,alignment = align_recovered(predicted,cloud,document)
            pose_source = 'recovered_and_aligned'
        frames = validate_cameras(document,names)
        progress(.5,desc='입력 점군의 표면을 연결해 메시를 만들고 있어요.')
        vertices,faces,colors = triangulate(cloud)
        progress(.75,desc='보이는 표면에 사진을 투영하고 있어요.')
        uv,view_ids,_ = camera_uv(vertices,faces,cloud,frames)
        coverage = float((view_ids>=0).mean())
        if coverage < .1: raise ValueError('사진이 메시 표면과 맞지 않아요. 사진·포즈·PLY가 같은 장면인지 확인해주세요.')
        atlas = build_atlas(photos)
        key = uuid.uuid4().hex
        directory = ROOT/key; directory.mkdir()
        digest = hashlib.sha256(vertices.tobytes()+faces.tobytes()).hexdigest()
        metadata = {'scene_id':key,'vertex_count':len(vertices),'face_count':len(faces),
            'image_count':len(photos),'textured_faces_ratio':round(coverage,3),
            'pose_source':pose_source,'geometry_sha256':digest,'geometry_preserved':True,
            'coordinate_system':'OpenCV','display_coordinate_system':'Y_UP',**alignment,
            'limitation':'Observed surfaces only; holes and texture seams may remain.'}
        np.savez_compressed(directory/'mesh.npz',vertices=vertices,faces=faces,colors=colors,uv=uv,view_ids=view_ids)
        atlas.save(directory/'original-atlas.png')
        pose_file = directory/'cameras.json'
        pose_file.write_text(json.dumps(document,ensure_ascii=False,indent=2))
        output = directory/'original.glb'
        export_scene(output,vertices,faces,uv,colors,view_ids,atlas,metadata)
        bundle = directory/'posed-images.zip'
        with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(pose_file,'cameras.json'); archive.write(ply,'scene.ply')
            for original,name in zip(images,names): archive.write(original,'images/'+name)
        for index,photo in enumerate(photos): photo.save(directory/f'photo-{index}.png')
        SCENES[key] = {'owner':session,'created':time.time(),'directory':directory,
                       'metadata':metadata,'image_count':len(photos)}
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
        with Image.open(directory/'original-atlas.png') as source: atlas = source.convert('RGB')
        photos = []
        for i in range(scene['image_count']):
            with Image.open(directory/f'photo-{i}.png') as source: photos.append(source.convert('RGB'))
        progress(.1,desc='원본 구조를 유지하며 재질과 분위기를 바꾸고 있어요.')
        edited = edit_images(atlas,photos,prompt,seed)
        progress(.85,desc='편집한 이미지를 고정된 메시 표면에 입히고 있어요.')
        with np.load(directory/'mesh.npz',allow_pickle=False) as mesh:
            metadata = {**scene['metadata'],'prompt':prompt,'seed':seed,'model':models.FLUX_REPO,
                        'model_revision':models.FLUX_REVISION,'geometry_preserved':True}
            stem = 'style-'+uuid.uuid4().hex[:12]
            texture = directory/(stem+'.png'); edited.save(texture)
            output = directory/(stem+'.glb')
            export_scene(output,mesh['vertices'],mesh['faces'],mesh['uv'],mesh['colors'],mesh['view_ids'],edited,metadata)
        progress(1,desc='새 분위기의 메시가 준비됐어요.')
        return str(output),str(texture),metadata
    except (ValueError,OSError,KeyError,TypeError) as error:
        raise gr.Error(str(error)) from None


with gr.Blocks(title='Pi3X Mesh Studio') as demo:
    gr.Markdown('# Pi3X Mesh Studio\n기존 Pi3X Space와 별도로 실행됩니다. 구조를 유지하고 재질·분위기를 바꿉니다.')
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
    prompt = gr.Textbox(label='원하는 재질과 분위기',placeholder='따뜻한 원목과 베이지 패브릭, 부드러운 오후 햇살')
    seed = gr.Number(value=0,precision=0,label='시드')
    change = gr.Button('재질·분위기 바꾸기')
    styled = gr.Model3D(label='텍스처 메시')
    texture = gr.File(label='텍스처 이미지')
    changed_metadata = gr.JSON(label='편집 정보')
    prepare.click(prepare_scene,[ply,images,poses,quality],[original,scene_id,cameras,metadata,bundle],api_name='prepare_scene',concurrency_limit=1,concurrency_id='mesh')
    change.click(restyle_scene,[scene_id,prompt,seed],[styled,texture,changed_metadata],api_name='restyle_scene',concurrency_limit=1,concurrency_id='mesh')
    state = gr.JSON(visible=False)
    demo.load(capabilities,outputs=state,api_name='capabilities',queue=False)
demo.queue(max_size=4,default_concurrency_limit=1)
if __name__ == '__main__':
    demo.launch(server_name='0.0.0.0',server_port=7860,share=False,ssr_mode=False,
                show_error=True,max_file_size='40mb')
