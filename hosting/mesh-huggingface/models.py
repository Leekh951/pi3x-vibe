"""Models are loaded ONLY in the new Space, never on the local development host."""
import gc
import math
import os
import subprocess
import sys
from pathlib import Path

os.environ['XFORMERS_DISABLED'] = '1'
import numpy as np
import torch
from PIL import Image,ImageOps
from huggingface_hub import hf_hub_download
from safetensors import safe_open

PI3_REVISION = '9fa3ddb3f8d53041f8b2738df404f62223bbaa7b'
PI3_WEIGHTS = 'bb1deea4d7423de5b30691739cb451a3f57dc1d5'
BASE_REPO = 'stable-diffusion-v1-5/stable-diffusion-v1-5'
BASE_REVISION = '451f4fe16113bff5a5d2269ed5ad43b0592e9a14'
DEPTH_REPO = 'lllyasviel/control_v11f1p_sd15_depth'
DEPTH_REVISION = '539f99181d33db39cf1af2e517cd8056785f0a87'
SAFETY_REVISION = 'cb41f3a270d63d454d385fc2e4f571c487c253c5'
PI3 = PIPE = CHECKER = PROCESSOR = None
ERRORS = {}


def initialize():
    global PI3,PIPE,CHECKER,PROCESSOR
    token = os.environ.get('HF_TOKEN')
    try:
        source = Path('/tmp/MESH_Pi3_source')
        if not (source/'.git').exists():
            subprocess.run(['git','clone','--filter=blob:none','--no-checkout','https://github.com/yyfz/Pi3.git',str(source)],check=True)
        subprocess.run(['git','-C',str(source),'checkout','--detach',PI3_REVISION],check=True)
        sys.path.insert(0,str(source))
        from pi3.models.pi3x import Pi3X
        checkpoint = hf_hub_download('yyfz233/Pi3X','model.safetensors',revision=PI3_WEIGHTS,token=token)
        with torch.device('cpu'): candidate = Pi3X(use_multimodal=False).eval()
        with safe_open(checkpoint,framework='pt',device='cpu') as handle:
            tensors = {name:handle.get_tensor(name) for name in candidate.state_dict()}
        candidate.load_state_dict(tensors,strict=True,assign=True)
        del tensors
        PI3 = candidate.to('cuda').eval()
        gc.collect()
    except Exception as error:
        ERRORS['poses'] = type(error).__name__
        print('Pi3X pose startup failed:',type(error).__name__,flush=True)
    try:
        from diffusers import ControlNetModel,StableDiffusionControlNetInpaintPipeline,UniPCMultistepScheduler
        from diffusers.pipelines.stable_diffusion.safety_checker import StableDiffusionSafetyChecker
        from transformers import CLIPImageProcessor
        CHECKER = StableDiffusionSafetyChecker.from_pretrained('CompVis/stable-diffusion-safety-checker',revision=SAFETY_REVISION,torch_dtype=torch.float16,token=token).to('cuda').eval()
        PROCESSOR = CLIPImageProcessor.from_pretrained('CompVis/stable-diffusion-safety-checker',revision=SAFETY_REVISION,token=token)
        control = ControlNetModel.from_pretrained(DEPTH_REPO,revision=DEPTH_REVISION,
            torch_dtype=torch.float16,variant='fp16',use_safetensors=True,token=token)
        candidate = StableDiffusionControlNetInpaintPipeline.from_pretrained(BASE_REPO,revision=BASE_REVISION,
            controlnet=control,torch_dtype=torch.float16,variant='fp16',use_safetensors=True,
            low_cpu_mem_usage=True,token=token,safety_checker=CHECKER,feature_extractor=PROCESSOR)
        candidate.scheduler = UniPCMultistepScheduler.from_config(candidate.scheduler.config)
        candidate.to('cuda'); candidate.vae.enable_tiling()
        PIPE = candidate

    except Exception as error:
        ERRORS['texture'] = type(error).__name__
        print('Texture startup failed:',type(error).__name__,'Check model approval and HF_TOKEN.',flush=True)


def load_images(paths):
    if not paths or not 2 <= len(paths) <= 8: raise ValueError('사진은 2–8장 필요해요.')
    photos = []
    for path in paths:
        if Path(path).stat().st_size > 15*1024*1024: raise ValueError('사진은 장당 15 MB 이하로 선택해주세요.')
        with Image.open(path) as image:
            if image.format not in {'JPEG','PNG','WEBP'} or min(image.size) < 28:
                raise ValueError('JPG, PNG, WEBP 원본 사진을 넣어주세요.')
            photo = ImageOps.exif_transpose(image).convert('RGB')
            photo.thumbnail((2048,2048),Image.Resampling.LANCZOS)
            photos.append(photo)
    return photos


@torch.inference_mode()
def recover(paths,quality):
    if PI3 is None: raise ValueError('포즈 복원 모델이 준비되지 않았어요. 포즈 JSON을 넣거나 서버 시작 로그를 확인해주세요.')
    photos = load_images(paths)
    width,height = photos[0].size
    limit = {'fast':90000,'detail':230000}.get(quality,90000)
    factor = math.sqrt(limit/(width*height))
    cols,rows = max(1,round(width*factor/14)),max(1,round(height*factor/14))
    while cols*rows*196 > limit:
        if cols/rows > width/height and cols > 1: cols -= 1
        elif rows > 1: rows -= 1
        else: cols -= 1
    size = (cols*14,rows*14)
    rgb = np.stack([np.asarray(p.resize(size,Image.Resampling.LANCZOS)) for p in photos])
    tensor = torch.from_numpy(rgb.copy()).permute(0,3,1,2).float().div_(255).unsqueeze(0).to('cuda')
    with torch.amp.autocast('cuda',dtype=torch.bfloat16): result = PI3(imgs=tensor)
    local = result['local_points'][0].float().cpu().numpy()
    poses = result['camera_poses'][0].float().cpu().numpy()
    scores = result['conf'][0,...,0].sigmoid().float().cpu().numpy()
    predicted = result['points'][0].float().cpu().numpy()
    yy,xx = np.mgrid[:size[1],:size[0]]
    frames = []
    for i,path in enumerate(paths):
        good = (scores[i]>.3)&np.isfinite(local[i]).all(axis=2)&(local[i,...,2]>0)
        rays = local[i,...,:2]/np.maximum(local[i,...,2:],1e-8)
        if good.sum() < 100: raise ValueError('카메라를 복원할 선명한 영역이 부족해요.')
        x = rays[...,0][good]; y = rays[...,1][good]
        fx,cx = np.linalg.lstsq(np.stack([x,np.ones_like(x)],axis=1),xx[good],rcond=None)[0]
        fy,cy = np.linalg.lstsq(np.stack([y,np.ones_like(y)],axis=1),yy[good],rcond=None)[0]
        if fx<=0 or fy<=0: raise ValueError('카메라 초점거리를 복원하지 못했어요.')
        residual = float(np.sqrt(np.mean((fx*x+cx-xx[good])**2+(fy*y+cy-yy[good])**2)))
        if residual > max(size)*.02: raise ValueError('카메라 투영 오차가 커요. 원래 포즈 JSON을 사용해주세요.')
        frames.append({'image':Path(path).name,'image_size':list(size),
            'intrinsics':[[float(fx),0,float(cx)],[0,float(fy),float(cy)],[0,0,1]],
            'camera_to_world':poses[i].tolist(),'intrinsics_fit_rmse_px':round(residual,3)})
    valid = (scores>.3)&np.isfinite(predicted).all(axis=-1)
    cloud = predicted[valid]
    cloud = cloud[::max(1,len(cloud)//40000)].copy()
    del tensor,result
    torch.cuda.empty_cache()
    return {'coordinate_system':'OpenCV','pose_convention':'camera_to_world','frames':frames},cloud


@torch.inference_mode()
def check_images(images):
    if CHECKER is None or PROCESSOR is None: raise ValueError('이미지 검사 모델이 준비되지 않았어요.')
    clip = PROCESSOR(images=images,return_tensors='pt').pixel_values.to('cuda',dtype=next(CHECKER.parameters()).dtype)
    _,flags = CHECKER(clip_input=clip,images=np.zeros((len(images),224,224,3),dtype=np.float32))
    if any(flags): raise ValueError('이미지 검사에서 처리할 수 없는 사진이 감지됐어요.')


@torch.inference_mode()
def paint_view(rendered,mask,depth,images,prompt,seed):
    if PIPE is None: raise ValueError('장면 텍스처 모델이 준비되지 않았어요. 새 Space의 서버 시작 로그를 확인해주세요.')
    check_images(images)
    instruction = ('An interior room, preserve the existing room layout, walls, floor and furniture silhouettes. '
        'Consistent surface materials across the whole interior scene, realistic textures, no people. '+prompt)
    result = PIPE(prompt=instruction,negative_prompt='people, text, watermark, blurry, distorted geometry',
        image=rendered,mask_image=mask,control_image=depth,width=rendered.width,height=rendered.height,
        strength=1.0,controlnet_conditioning_scale=1.0,guidance_scale=7.0,num_inference_steps=20,
        generator=torch.Generator(device='cuda').manual_seed(seed))
    if any(result.nsfw_content_detected or []): raise ValueError('이미지 검사에서 처리할 수 없는 결과가 감지됐어요.')
    output = result.images[0].convert('RGB')
    check_images([output])
    # Preserve all previously painted surfaces and background exactly even if the
    # denoiser's latent blending changes pixels outside the requested mask.
    return Image.composite(output,rendered,mask)
