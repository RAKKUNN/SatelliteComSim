import sys
import numpy as np
import trimesh
from PIL import Image
from PyQt5.QtWidgets import QOpenGLWidget
from PyQt5.QtCore import Qt, QTimer
from OpenGL.GL import *
from OpenGL.GLU import gluPerspective

def load_model(filepath, texture_path=None):
    # trimesh를 사용하여 GLB 파일을 로드합니다.
    mesh = trimesh.load(filepath, force='scene')
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate(mesh.geometry.values())
    vertices = mesh.vertices.astype(np.float32)
    indices = mesh.faces.astype(np.uint32).flatten()
    texcoords = mesh.visual.uv.astype(np.float32) if (mesh.visual.kind == 'texture' and mesh.visual.uv is not None) else None

    texture = None
    if texture_path:
        texture = Image.open(texture_path).convert("RGB")
    return vertices, indices, texcoords, texture

class EarthSatelliteView(QOpenGLWidget):
    def __init__(self, model_path="earth.glb", texture_path="textures/image_0.png", parent=None):
        super().__init__(parent)
        self.model_path = model_path
        self.texture_path = texture_path
        self.vbo = None
        self.ebo = None
        self.tbo = None
        self.texture_id = None
        self.num_indices = 0
        self.vertices = None
        self.rotation = [0, 0]  # [x, y] 회전값
        self.zoom = -2.5        # 초기 줌 값
        self.last_pos = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(16)

    def initializeGL(self):
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_TEXTURE_2D)

        # 모델과 텍스처 로드
        vertices, indices, texcoords, texture = load_model(self.model_path, self.texture_path)
        self.vertices = vertices
        self.num_indices = len(indices)

        # VBO 생성
        self.vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)

        # EBO 생성
        self.ebo = glGenBuffers(1)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)

        # TBO (텍스처 좌표)가 있을 경우 생성
        if texcoords is not None:
            self.tbo = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self.tbo)
            glBufferData(GL_ARRAY_BUFFER, texcoords.nbytes, texcoords, GL_STATIC_DRAW)

        # 텍스처 업로드
        if texture is not None:
            tex_data = texture.tobytes("raw", "RGB", 0, -1)
            width, height = texture.size
            self.texture_id = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, self.texture_id)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, width, height, 0, GL_RGB, GL_UNSIGNED_BYTE, tex_data)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glBindTexture(GL_TEXTURE_2D, 0)

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        aspect = w / h if h else 1
        gluPerspective(45.0, aspect, 0.1, 100.0)
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        # 카메라 위치 설정
        glTranslatef(0.0, 0.0, self.zoom)
        glRotatef(self.rotation[0], 1, 0, 0)
        glRotatef(self.rotation[1], 0, 1, 0)

        glEnableClientState(GL_VERTEX_ARRAY)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glVertexPointer(3, GL_FLOAT, 0, None)

        if self.texture_id and self.tbo:
            glEnable(GL_TEXTURE_2D)
            glEnableClientState(GL_TEXTURE_COORD_ARRAY)
            glBindTexture(GL_TEXTURE_2D, self.texture_id)
            glBindBuffer(GL_ARRAY_BUFFER, self.tbo)
            glTexCoordPointer(2, GL_FLOAT, 0, None)

        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glDrawElements(GL_TRIANGLES, self.num_indices, GL_UNSIGNED_INT, None)

        if self.texture_id:
            glBindTexture(GL_TEXTURE_2D, 0)
            glDisableClientState(GL_TEXTURE_COORD_ARRAY)

        glDisableClientState(GL_VERTEX_ARRAY)

    def mousePressEvent(self, event):
        self.last_pos = event.pos()

    def mouseMoveEvent(self, event):
        if self.last_pos is None:
            return
        dx = event.x() - self.last_pos.x()
        dy = event.y() - self.last_pos.y()
        if event.buttons() & Qt.LeftButton:
            self.rotation[0] += dy
            self.rotation[1] += dx
        self.last_pos = event.pos()
        self.update()

    def wheelEvent(self, event):
        delta = event.angleDelta().y() / 120  # 한 notch 당 15도
        self.zoom += delta * 0.3
        self.update()

if __name__ == "__main__":
    # 간단한 테스트를 위한 standalone 실행 코드입니다.
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    viewer = EarthSatelliteView("earth.glb", "textures/image_0.png")
    viewer.resize(800, 600)
    viewer.show()
    sys.exit(app.exec_())

