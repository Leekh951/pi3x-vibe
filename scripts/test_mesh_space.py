"""Validate portable cameras and real GLB contents without installing/GPU/network."""
import copy
import importlib.util
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from build_mesh_space import ROOT,build


def load(name):
    spec=importlib.util.spec_from_file_location('mesh_test_'+name,ROOT/'hosting/mesh-huggingface'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


contracts=load('contracts');writer=load('glb')


def read_glb(data):
    magic,version,length=struct.unpack_from('<III',data)
    assert (magic,version,length)==(0x46546c67,2,len(data))
    length,kind=struct.unpack_from('<II',data,12);assert kind==0x4e4f534a
    document=json.loads(data[20:20+length])
    offset=20+length
    bin_length,kind=struct.unpack_from('<II',data,offset);assert kind==0x004e4942
    binary=data[offset+8:];assert len(binary)==bin_length
    return document,binary


def png(pixel):
    def chunk(kind,value):
        return struct.pack('>I',len(value))+kind+value+struct.pack('>I',zlib.crc32(kind+value))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0'+bytes(pixel)))+chunk(b'IEND',b'')


class MeshTests(unittest.TestCase):
    def camera_document(self):
        frame={'image':'one.jpg','image_size':[960,540],
               'intrinsics':[[800,0,480],[0,800,270],[0,0,1]],
               'camera_to_world':[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]}
        second=copy.deepcopy(frame);second['image']='two.jpg';second['camera_to_world'][0][3]=1
        return {'coordinate_system':'OpenCV','pose_convention':'camera_to_world','frames':[second,frame]}

    def test_camera_names_bind_to_images_instead_of_upload_order(self):
        frames=contracts.validate_cameras(self.camera_document(),['one.jpg','two.jpg'])
        self.assertEqual([f['image'] for f in frames],['one.jpg','two.jpg'])
        self.assertEqual(frames[1]['camera_to_world'][0][3],1)

    def test_invalid_pose_and_coordinates_are_rejected(self):
        for change in ('convention','nan','scale','reflection','duplicate','missing','negative_focal'):
            document=self.camera_document();frame=document['frames'][0]
            if change=='convention': document['pose_convention']='world_to_camera'
            if change=='nan': frame['camera_to_world'][0][3]=float('nan')
            if change=='scale': frame['camera_to_world'][0][0]=2
            if change=='reflection': frame['camera_to_world'][0][0]=-1
            if change=='duplicate': frame['image']='one.jpg'
            if change=='missing': frame['image']='other.jpg'
            if change=='negative_focal': frame['intrinsics'][0][0]=-1
            with self.subTest(change=change),self.assertRaises(ValueError):
                contracts.validate_cameras(document,['one.jpg','two.jpg'])

    def test_texture_is_embedded_and_styles_preserve_geometry(self):
        vertices=[[0,0,2],[1,0,2],[0,1,2]];faces=[[0,1,2]];uv=[[0,0],[1,0],[0,1]]
        with tempfile.TemporaryDirectory() as folder:
            original=Path(folder)/'original.glb';styled=Path(folder)/'styled.glb'
            writer.write_glb(original,vertices,faces,uv,png([255,255,255]),[[1,1,1]]*3)
            writer.write_glb(styled,vertices,faces,uv,png([130,80,30]),[[1,1,1]]*3)
            a,ab=read_glb(original.read_bytes());b,bb=read_glb(styled.read_bytes())
            for name in ('POSITION','TEXCOORD_0'):
                ai=a['meshes'][0]['primitives'][0]['attributes'][name]
                bi=b['meshes'][0]['primitives'][0]['attributes'][name]
                av=a['bufferViews'][a['accessors'][ai]['bufferView']]
                bv=b['bufferViews'][b['accessors'][bi]['bufferView']]
                self.assertEqual(ab[av['byteOffset']:av['byteOffset']+av['byteLength']],bb[bv['byteOffset']:bv['byteOffset']+bv['byteLength']])
            self.assertEqual(a['nodes'][0]['scale'],[1,-1,-1])
            upright=Path(folder)/'upright.glb'
            writer.write_glb(upright,vertices,faces,uv,png([255,255,255]),[[1,1,1]]*3,{'coordinate_system':'Y_UP'})
            up,_=read_glb(upright.read_bytes())
            self.assertEqual(up['nodes'][0]['scale'],[1,1,1],'saved upright PLYs are not flipped twice')
            image=b['bufferViews'][b['images'][0]['bufferView']]
            self.assertEqual(bb[image['byteOffset']:image['byteOffset']+image['byteLength']],png([130,80,30]))
            self.assertNotEqual(original.read_bytes(),styled.read_bytes())

    def test_upload_is_self_contained_and_separate(self):
        import zipfile
        (ROOT/'dist').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'dist') as folder:
            output,archive=build(Path(folder)/'mesh')
            with zipfile.ZipFile(archive) as bundle:
                self.assertEqual(set(bundle.namelist()),{p.name for p in output.iterdir() if p.is_file()})
                for required in ('app.py','models.py','geometry.py','glb.py','contracts.py','requirements.txt','packages.txt','README.md'):
                    self.assertIn(required,bundle.namelist())
                self.assertNotIn('backend.py',bundle.namelist())


if __name__=='__main__': unittest.main()
