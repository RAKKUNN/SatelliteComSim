import trimesh
from PIL import Image
import numpy as np

def load_model_trimesh(filepath):
    """
    GLB 파일을 load할 때 force='scene' 옵션으로 전체 scene을 로드한 후,
    모든 geometry를 순회하여 텍스처 정보가 있는 메쉬를 선택합니다.
    텍스처 정보가 없을 경우, 재질의 baseColorFactor가 있으면 그 색상으로 1x1 이미지를 생성합니다.
    """
    scene = trimesh.load(filepath, force='scene')
    if not scene.geometry:
        raise Exception("모델에 지오메트리가 없습니다.")
    
    selected_mesh = None
    texture = None
    
    # 모든 geometry를 순회하면서 텍스처 정보를 찾습니다.
    for name, mesh in scene.geometry.items():
        print(f"메쉬: {name}")
        if hasattr(mesh.visual, 'material'):
            material = mesh.visual.material
            # 디버깅: 재질 속성 출력
            print("material properties:", material.properties)
            if hasattr(material, 'image') and material.image is not None:
                texture = material.image.convert("RGB")
                print(f"'{name}' 메쉬에서 텍스처 로딩 성공")
                selected_mesh = mesh
                break
            # 만약 텍스처 이미지가 없고, 기본 색상 정보가 있다면 사용
            elif 'baseColorFactor' in material.properties:
                # baseColorFactor는 [r, g, b, a] 값 (0~1)로 제공됨
                color = material.properties['baseColorFactor']
                color = tuple(int(c * 255) for c in color[:3])
                texture = Image.new("RGB", (1,1), color)
                print(f"'{name}' 메쉬에서 기본 색상 {color} 사용")
                selected_mesh = mesh
                break
        if hasattr(mesh.visual, 'kind') and mesh.visual.kind == 'texture':
            selected_mesh = mesh
            print(f"'{name}' 메쉬가 텍스처 정보를 가진 것으로 추정됨")
            break

    if selected_mesh is None:
        selected_mesh = list(scene.geometry.values())[0]
        print("텍스처 정보가 있는 메쉬를 찾지 못했습니다. 첫 번째 메쉬를 사용합니다.")
    
    vertices = np.array(selected_mesh.vertices, dtype=np.float32)
    indices = np.array(selected_mesh.faces, dtype=np.uint32).flatten()
    return vertices, indices, texture

