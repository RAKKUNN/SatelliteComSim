import sys
import numpy as np
import trimesh
from PIL import Image
from PyQt5.QtWidgets import QApplication, QOpenGLWidget
from PyQt5.QtCore import Qt
from OpenGL.GL import *
from OpenGL.GLU import gluPerspective


def load_model(filepath, texture_path=None):
    mesh = trimesh.load(filepath, force='scene')
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate(mesh.geometry.values())

    vertices = mesh.vertices.astype(np.float32)
    indices = mesh.faces.astype(np.uint32).flatten()
    texcoords = mesh.visual.uv.astype(np.float32) if mesh.visual.kind == 'texture' else None

    texture = None
    if texture_path:
        texture = Image.open(texture_path).convert("RGB")

    return vertices, indices, texcoords, texture


class InteractiveGLBViewer(QOpenGLWidget):
    def __init__(self, model_path, texture_path=None):
        super().__init__()
        self.model_path = model_path
        self.texture_path = texture_path
        self.vbo = self.ebo = self.tbo = self.texture_id = None
        self.num_indices = 0
        self.vertices = None
        self.rotation = [0, 0]
        self.zoom = -2.5
        self.last_pos = None

    def initializeGL(self):
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_TEXTURE_2D)

        v, i, uv, tex = load_model(self.model_path, self.texture_path)
        self.vertices = v
        self.num_indices = len(i)

        self.vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, v.nbytes, v, GL_STATIC_DRAW)

        self.ebo = glGenBuffers(1)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, i.nbytes, i, GL_STATIC_DRAW)

        if uv is not None:
            self.tbo = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self.tbo)
            glBufferData(GL_ARRAY_BUFFER, uv.nbytes, uv, GL_STATIC_DRAW)

        if tex is not None:
            tex_data = tex.tobytes("raw", "RGB", 0, -1)
            width, height = tex.size
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
        delta = event.angleDelta().y() / 120  # one notch = 15 degrees
        self.zoom += delta * 0.3
        self.update()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = InteractiveGLBViewer("earth.glb", "textures/image_0.png")
    viewer.resize(800, 600)
    viewer.show()
    sys.exit(app.exec_())

