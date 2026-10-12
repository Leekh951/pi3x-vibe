import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';
import { GLTFLoader } from './vendor/GLTFLoader.js';

export class MeshViewer {
  constructor(mount) {
    this.mount=mount;this.scene=new THREE.Scene();
    this.renderer=new THREE.WebGLRenderer({antialias:true});
    this.renderer.setPixelRatio(Math.min(devicePixelRatio,2));this.renderer.setClearColor(0x101a23);
    mount.append(this.renderer.domElement);
    this.camera=new THREE.PerspectiveCamera(43,1,.01,2000);
    this.controls=new OrbitControls(this.camera,this.renderer.domElement);
    this.controls.enableDamping=true;
    this.observer=new ResizeObserver(()=>this.resize());this.observer.observe(mount);
    this.renderer.setAnimationLoop(()=>{this.controls.update();this.renderer.render(this.scene,this.camera);});
    this.resize();
  }
  resize() {
    const {width,height}=this.mount.getBoundingClientRect();if(!width||!height)return;
    this.renderer.setSize(width,height);this.camera.aspect=width/height;this.camera.updateProjectionMatrix();
  }
  disposeRoot(root) {
    const textures=new Set();
    root.traverse(node=>{node.geometry?.dispose();const materials=Array.isArray(node.material)?node.material:[node.material];
      for(const material of materials)if(material){if(material.map)textures.add(material.map);material.dispose();}});
    for(const texture of textures)texture.dispose();
  }
  async show(buffer) {
    const gltf=await new GLTFLoader().parseAsync(buffer,'');
    const root=gltf.scene;
    const bounds=new THREE.Box3().setFromObject(root);
    if(bounds.isEmpty()){this.disposeRoot(root);throw Error('메시에 표시할 면이 없어요.');}
    root.traverse(node=>{if(node.isMesh){const previous=node.material;
      node.material=new THREE.MeshBasicMaterial({map:previous.map,color:previous.color,
        vertexColors:!!node.geometry.attributes.color,side:THREE.DoubleSide});previous.dispose();}});
    if(this.root){this.scene.remove(this.root);this.disposeRoot(this.root);}
    this.root=root;this.scene.add(root);
    const center=bounds.getCenter(new THREE.Vector3());
    const radius=bounds.getSize(new THREE.Vector3()).length()/2;
    const fov=Math.min(THREE.MathUtils.degToRad(this.camera.fov/2),Math.atan(Math.tan(THREE.MathUtils.degToRad(this.camera.fov/2))*this.camera.aspect));
    const distance=radius/Math.sin(fov)*1.08;
    this.controls.target.copy(center);this.camera.position.copy(center).addScaledVector(new THREE.Vector3(1,.65,1.2).normalize(),distance);
    this.camera.near=Math.max(distance/1000,.001);this.camera.far=distance*100;
    this.camera.updateProjectionMatrix();this.controls.minDistance=distance*.08;this.controls.maxDistance=distance*8;this.controls.update();
  }
}
