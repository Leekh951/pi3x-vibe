"""Small uncompressed GLB writer. No external exporter or shader extensions."""
import json
import math
import struct


def write_glb(path, vertices, faces, uv, texture_png, colors, extras=None):
    # Both original and styled exports use identical vertices/faces/UVs.
    # UV coordinates refer to a top-left image origin; glTF uses the same origin.
    document = {'asset': {'version':'2.0', 'generator':'Pi3X Mesh Studio'},
                'scene':0, 'scenes':[{'nodes':[0]}],
                'nodes':[{'mesh':0, 'scale':[1,-1,-1]}],
                'meshes':[{'primitives':[]}], 'bufferViews':[], 'accessors':[],
                'materials':[{'doubleSided':True, 'pbrMetallicRoughness':{
                    'baseColorTexture':{'index':0}, 'metallicFactor':0, 'roughnessFactor':1}}],
                'textures':[{'source':0, 'sampler':0}],
                'samplers':[{'magFilter':9729, 'minFilter':9729, 'wrapS':33071, 'wrapT':33071}],
                'extras':extras or {}}
    binary = bytearray()

    def view(data, target=None):
        binary.extend(b'\0' * (-len(binary) % 4))
        record = {'buffer':0, 'byteOffset':len(binary), 'byteLength':len(data)}
        if target: record['target'] = target
        document['bufferViews'].append(record)
        binary.extend(data)
        return len(document['bufferViews'])-1

    def accessor(rows, width, bounds=False):
        values = [float(x) for row in rows for x in row]
        if not values or any(not math.isfinite(x) for x in values):
            raise ValueError('메시 데이터에 유효하지 않은 좌표가 있어요.')
        record = {'bufferView':view(struct.pack('<'+'f'*len(values), *values),34962),
                  'componentType':5126, 'count':len(rows), 'type':{2:'VEC2',3:'VEC3',4:'VEC4'}[width]}
        if bounds:
            record.update(min=[min(r[i] for r in rows) for i in range(width)],
                          max=[max(r[i] for r in rows) for i in range(width)])
        document['accessors'].append(record)
        return len(document['accessors'])-1

    # Flat triangle corners keep camera UV seams from moving the geometry.
    positions = [vertices[int(i)] for face in faces for i in face]
    corner_colors = [colors[int(i)] for face in faces for i in face]
    attributes = {'POSITION':accessor(positions,3,True), 'TEXCOORD_0':accessor(uv,2),
                  'COLOR_0':accessor(corner_colors,3)}
    document['meshes'][0]['primitives'].append({'attributes':attributes, 'material':0, 'mode':4})
    document['images'] = [{'bufferView':view(texture_png), 'mimeType':'image/png'}]
    binary.extend(b'\0' * (-len(binary) % 4))
    document['buffers'] = [{'byteLength':len(binary)}]
    encoded = json.dumps(document,ensure_ascii=False,separators=(',',':')).encode('utf8')
    encoded += b' ' * (-len(encoded) % 4)
    data = (struct.pack('<III',0x46546c67,2,12+8+len(encoded)+8+len(binary))
            +struct.pack('<II',len(encoded),0x4e4f534a)+encoded
            +struct.pack('<II',len(binary),0x004e4942)+binary)
    path.write_bytes(data)
    return str(path)
