#!/usr/bin/env python3
import sys
import ctypes
import math
import numpy as np
import trimesh
from PIL import Image
from PyQt5.QtWidgets import QOpenGLWidget, QApplication
from PyQt5.QtCore import Qt, QTimer
from OpenGL.GL import *
from OpenGL.GLU import gluPerspective

def load_model(filepath, texture_path=None):
    mesh = trimesh.load(filepath, force='scene')
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate(mesh.geometry.values())
    vertices = mesh.vertices.astype(np.float32)
    indices = mesh.faces.astype(np.uint32).flatten()
    texcoords = None
    if hasattr(mesh.visual, 'uv') and mesh.visual.uv is not None:
        texcoords = mesh.visual.uv.astype(np.float32)
    texture = None
    if texture_path:
        texture = Image.open(texture_path).convert('RGB')
    return vertices, indices, texcoords, texture

class EarthSatelliteView(QOpenGLWidget):
    def __init__(self, model_path='earth.glb', texture_path='textures/image_0.png',
                 bg_image_path='textures/background.jpg', sat_model_path='textures/satellite.glb',
                 sat_texture_path='textures/satellite_texture.jpg', parent=None):
        super().__init__(parent)
        # Paths
        self.model_path = model_path
        self.texture_path = texture_path
        self.bg_image_path = bg_image_path
        self.sat_model_path = sat_model_path
        self.sat_texture_path = sat_texture_path
        # GL buffers & textures
        self.bg_vbo = None
        self.bg_texture = 0
        self.earth_vbo = self.earth_ebo = self.earth_tbo = None
        self.earth_texture = 0
        self.sat_vbo = self.sat_ebo = self.sat_tbo = None
        self.sat_texture = 0
        # Counts
        self.earth_index_count = 0
        self.sat_index_count = 0
        # Radii
        self.earth_radius = 1.0
        self.orbital_radius = 1.0
        # Camera control
        self.rotation = [30.0, -45.0]
        self.zoom = -10.0
        self.last_pos = None
        # Satellite parameters
        self.sat_type = '소형 위성'
        self.sat_size = 10.0
        self.sat_speed = 0.05
        self.orbital_radius_units = 300.0
        self.inclination = 45.0
        self.eccentricity = 0.0
        self.frequency = 2.4
        self.antenna_gain = 10.0
        self.transmit_power = 0.0
        self.sat_angle = 0.0
        # Timer (~60fps)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_timer)
        self.timer.start(16)
        # Enable mouse events
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

    def on_timer(self):
        self.sat_angle = (self.sat_angle + self.sat_speed) % 360.0
        self.update()

    def initializeGL(self):
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_TEXTURE_2D)
        glClearColor(0.0, 0.0, 0.0, 1.0)
        # Background quad
        bg = np.array([-1,-1,0,0, 1,-1,1,0, 1,1,1,1, -1,1,0,1], dtype=np.float32)
        self.bg_vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.bg_vbo)
        glBufferData(GL_ARRAY_BUFFER, bg.nbytes, bg, GL_STATIC_DRAW)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        # Background texture
        img = Image.open(self.bg_image_path).convert('RGB')
        w, h = img.size
        data = img.tobytes('raw','RGB',0,-1)
        self.bg_texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.bg_texture)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, w, h, 0, GL_RGB, GL_UNSIGNED_BYTE, data)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glBindTexture(GL_TEXTURE_2D, 0)
        # Load Earth model
        verts, inds, uvs, tex = load_model(self.model_path, self.texture_path)
        raw_radius = float(np.max(np.linalg.norm(verts, axis=1)))
        verts *= 0.4
        self.earth_radius = raw_radius * 0.4
        self.orbital_radius = self.earth_radius * (self.orbital_radius_units / 100.0 + 1.0)
        self.zoom = -self.earth_radius * 4.0
        self.earth_index_count = len(inds)
        # Earth buffers
        self.earth_vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.earth_vbo)
        glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_STATIC_DRAW)
        self.earth_ebo = glGenBuffers(1)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.earth_ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, inds.nbytes, inds, GL_STATIC_DRAW)
        if uvs is not None:
            self.earth_tbo = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self.earth_tbo)
            glBufferData(GL_ARRAY_BUFFER, uvs.nbytes, uvs, GL_STATIC_DRAW)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)
        # Earth texture
        if tex is not None:
            tw, th = tex.size
            tdata = tex.tobytes('raw','RGB',0,-1)
            self.earth_texture = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, self.earth_texture)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, tw, th, 0, GL_RGB, GL_UNSIGNED_BYTE, tdata)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glBindTexture(GL_TEXTURE_2D, 0)
        # Build satellite geometry
        self._build_satellite()

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45.0, w/h if h else 1.0, 0.1, 100.0)
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        # Draw background
        glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity(); glOrtho(-1,1,-1,1,-1,1)
        glMatrixMode(GL_MODELVIEW); glPushMatrix(); glLoadIdentity(); glDisable(GL_DEPTH_TEST)
        glBindBuffer(GL_ARRAY_BUFFER, self.bg_vbo); glEnableClientState(GL_VERTEX_ARRAY)
        glVertexPointer(2, GL_FLOAT, 16, ctypes.c_void_p(0)); glEnableClientState(GL_TEXTURE_COORD_ARRAY)
        glTexCoordPointer(2, GL_FLOAT, 16, ctypes.c_void_p(8)); glBindTexture(GL_TEXTURE_2D, self.bg_texture)
        glDrawArrays(GL_QUADS, 0, 4); glDisableClientState(GL_TEXTURE_COORD_ARRAY); glDisableClientState(GL_VERTEX_ARRAY)
        glBindTexture(GL_TEXTURE_2D, 0); glEnable(GL_DEPTH_TEST); glPopMatrix()
        glMatrixMode(GL_PROJECTION); glPopMatrix(); glMatrixMode(GL_MODELVIEW); glClear(GL_DEPTH_BUFFER_BIT)
        # Camera transform
        glLoadIdentity(); glTranslatef(0,0,self.zoom); glRotatef(self.rotation[0],1,0,0); glRotatef(self.rotation[1],0,1,0)
        # Earth
        glBindTexture(GL_TEXTURE_2D,self.earth_texture); glBindBuffer(GL_ARRAY_BUFFER,self.earth_vbo)
        glEnableClientState(GL_VERTEX_ARRAY); glVertexPointer(3,GL_FLOAT,0,ctypes.c_void_p(0))
        if hasattr(self,'earth_tbo') and self.earth_tbo:
            glEnableClientState(GL_TEXTURE_COORD_ARRAY); glBindBuffer(GL_ARRAY_BUFFER,self.earth_tbo); glTexCoordPointer(2,GL_FLOAT,0,ctypes.c_void_p(0))
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER,self.earth_ebo); glDrawElements(GL_TRIANGLES,self.earth_index_count,GL_UNSIGNED_INT,ctypes.c_void_p(0))
        glDisableClientState(GL_VERTEX_ARRAY);
        if hasattr(self,'earth_tbo') and self.earth_tbo: glDisableClientState(GL_TEXTURE_COORD_ARRAY)
        # Satellite
        theta=math.radians(self.sat_angle); incl=math.radians(self.inclination)
        x=self.orbital_radius*math.cos(theta); z=self.orbital_radius*math.sin(theta)
        y=z*math.sin(incl); z*=math.cos(incl)
        glPushMatrix(); glTranslatef(x,y,z)
        forward=np.array([0.0,-1.0,0.0],np.float32); target=np.array([-x,-y,-z],np.float32)
        if np.linalg.norm(target)>1e-6:
            target/=np.linalg.norm(target); axis=np.cross(forward,target)
            if np.linalg.norm(axis)>1e-6:
                axis/=np.linalg.norm(axis); cosang=np.dot(forward,target)
                angle=math.degrees(math.acos(max(-1.0,min(1.0,cosang)))); glRotatef(angle,axis[0],axis[1],axis[2])
        glBindTexture(GL_TEXTURE_2D,self.sat_texture); glBindBuffer(GL_ARRAY_BUFFER,self.sat_vbo)
        glEnableClientState(GL_VERTEX_ARRAY); glVertexPointer(3,GL_FLOAT,0,ctypes.c_void_p(0))
        if hasattr(self,'sat_tbo') and self.sat_tbo: glEnableClientState(GL_TEXTURE_COORD_ARRAY); glBindBuffer(GL_ARRAY_BUFFER,self.sat_tbo); glTexCoordPointer(2,GL_FLOAT,0,ctypes.c_void_p(0))
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER,self.sat_ebo); glDrawElements(GL_TRIANGLES,self.sat_index_count,GL_UNSIGNED_INT,ctypes.c_void_p(0))
        glDisableClientState(GL_VERTEX_ARRAY)
        if hasattr(self,'sat_tbo') and self.sat_tbo: glDisableClientState(GL_TEXTURE_COORD_ARRAY)
        glBindTexture(GL_TEXTURE_2D,0); glPopMatrix()

    # Mouse and wheel events
    def mousePressEvent(self, event):
        self.last_pos = event.pos()

    def mouseMoveEvent(self, event):
        if self.last_pos and event.buttons() & Qt.LeftButton:
            dx = event.x() - self.last_pos.x()
            dy = event.y() - self.last_pos.y()
            self.rotation[0] += dy
            self.rotation[1] += dx
            self.update()
        self.last_pos = event.pos()

    def wheelEvent(self, event):
        self.zoom += event.angleDelta().y() / 120 * 0.3
        self.update()

    def _build_satellite(self):
        verts, inds, uvs, tex = load_model(self.sat_model_path, self.sat_texture_path)
        verts *= (self.sat_size / 50.0 * self.earth_radius)
        self.sat_index_count = len(inds)
        self.sat_vbo = glGenBuffers(1); glBindBuffer(GL_ARRAY_BUFFER,self.sat_vbo); glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_STATIC_DRAW)
        self.sat_ebo = glGenBuffers(1); glBindBuffer(GL_ELEMENT_ARRAY_BUFFER,self.sat_ebo); glBufferData(GL_ELEMENT_ARRAY_BUFFER, inds.nbytes, inds, GL_STATIC_DRAW)
        if uvs is not None: self.sat_tbo = glGenBuffers(1); glBindBuffer(GL_ARRAY_BUFFER,self.sat_tbo); glBufferData(GL_ARRAY_BUFFER, uvs.nbytes, uvs, GL_STATIC_DRAW)
        glBindBuffer(GL_ARRAY_BUFFER,0); glBindBuffer(GL_ELEMENT_ARRAY_BUFFER,0)
        if tex is not None:
            sw,sh=tex.size; sdata=tex.tobytes('raw','RGB',0,-1)
            self.sat_texture=glGenTextures(1); glBindTexture(GL_TEXTURE_2D,self.sat_texture)
            glTexImage2D(GL_TEXTURE_2D,0,GL_RGB,sw,sh,0,GL_RGB,GL_UNSIGNED_BYTE,sdata)
            glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_LINEAR); glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_LINEAR)
            glBindTexture(GL_TEXTURE_2D,0)

    def updateSatelliteParameters(self, sat_type, sat_size, sat_speed,
                                  orbital_radius, inclination,
                                  eccentricity, frequency,
                                  antenna_gain, transmit_power):
        self.sat_type = sat_type
        self.sat_size = sat_size
        self.sat_speed = sat_speed
        self.orbital_radius_units = orbital_radius
        self.inclination = inclination
        self.eccentricity = eccentricity
        self.frequency = frequency
        self.antenna_gain = antenna_gain
        self.transmit_power = transmit_power
        self._build_satellite()

    def getCurrentParameters(self):
        return {
            'sat_type': self.sat_type,
            'sat_size': self.sat_size,
            'sat_speed': self.sat_speed,
            'orbital_radius': self.orbital_radius_units,
            'inclination': self.inclination,
            'eccentricity': self.eccentricity,
            'frequency': self.frequency,
            'antenna_gain': self.antenna_gain,
            'transmit_power': self.transmit_power
        }

if __name__=='__main__':
    app = QApplication(sys.argv)
    view = EarthSatelliteView()
    view.resize(800,600)
    view.show()
    sys.exit(app.exec_())

