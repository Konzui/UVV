"""
UVV Projection Utils
3D to 2D projection utilities for world orientation
"""

import math
from mathutils import Vector
from .constants import Planes
from .generic_helpers import MeshBuilder


class pVector:
    """Projection vector with angle calculation"""

    def __init__(self, vec) -> None:
        self.start = vec[0]
        self.end = vec[1]
        self.vec = self.end - self.start
        self.length = self.get_length()
        self.angle_to_y = self.angle_to_y_2d()

    def get_length(self):
        return self.vec.magnitude

    def angle_to_y_2d(self):
        return self.vec.angle_signed(Planes.axis_y, 0)


class Projection:
    """Projects 3D edge to 2D based on axis"""

    def __init__(self, ma_transform, bm, edge) -> None:
        self.ma_tr = ma_transform
        self.bm = bm
        self.edge = edge
        self.point_01 = self.ma_tr @ self.edge.vert.mesh_vert.co
        self.point_02 = self.ma_tr @ self.edge.other_vert.mesh_vert.co
        self.reversed = False
        self._set_orientation()
        self.anchor = self.edge.vert.uv_co
        self.projected = []
        self.real_length = edge.mesh_edge.calc_length()

    def uni_project(self, axis):
        """Universal projection based on axis"""
        solver = {
            "x": self.project_x(),
            "y": self.project_y(),
            "z": self.project_z(),
            "-x": self.project_x_negative(),
            "-y": self.project_y_negative(),
            "-z": self.project_z_negative()
        }
        return solver[axis]

    def project_to_cluster(self, cluster_normal):
        """Project to cluster normal plane"""
        v1 = self.project_onto_plane(self.point_01, cluster_normal)
        v2 = self.project_onto_plane(self.point_02, cluster_normal)
        projection = Vector((v1[1], v1[2])), Vector((v2[1], v2[2]))
        return pVector(projection)

    def _set_orientation(self):
        """Orient edge from bottom to top"""
        if (self.point_01).z > (self.point_02).z:
            self.edge.reverse()
            store = self.point_01
            self.point_01 = self.point_02
            self.point_02 = store
            self.reversed = True

    def project_x_negative(self):
        v1 = self.project_onto_plane(self.point_01, Planes.x3_negative)
        v2 = self.project_onto_plane(self.point_02, Planes.x3_negative)
        projection = Vector((v1[1], v1[2])), Vector((v2[1], v2[2]))
        return pVector(projection)

    def project_y_negative(self):
        v1 = self.project_onto_plane(self.point_01, Planes.y3_negative)
        v2 = self.project_onto_plane(self.point_02, Planes.y3_negative)
        projection = Vector((v1[0], v1[2])), Vector((v2[0], v2[2]))
        return pVector(projection)

    def project_z_negative(self):
        v1 = self.project_onto_plane(self.point_01, Planes.z3_negative)
        v2 = self.project_onto_plane(self.point_02, Planes.z3_negative)
        projection = Vector((v1[0], v1[1])), Vector((v2[0], v2[1]))
        return pVector(projection)

    def project_x(self):
        v1 = self.project_onto_plane(self.point_01, Planes.x3)
        v2 = self.project_onto_plane(self.point_02, Planes.x3)
        projection = Vector((v1[1], v1[2])), Vector((v2[1], v2[2]))
        return pVector(projection)

    def project_y(self):
        v1 = self.project_onto_plane(self.point_01, Planes.y3)
        v2 = self.project_onto_plane(self.point_02, Planes.y3)
        projection = Vector((v1[0], v1[2])), Vector((v2[0], v2[2]))
        return pVector(projection)

    def project_z(self):
        v1 = self.project_onto_plane(self.point_01, Planes.z3)
        v2 = self.project_onto_plane(self.point_02, Planes.z3)
        projection = Vector((v1[0], v1[1])), Vector((v2[0], v2[1]))
        return pVector(projection)

    def project_uv(self):
        """Project UV coordinates"""
        return pVector((self.edge.vert.uv_co, self.edge.other_vert.uv_co))

    def dot_product(self, x, y):
        return sum([x[i] * y[i] for i in range(len(x))])

    def norm(self, x):
        return math.sqrt(self.dot_product(x, x))

    def normalize(self, x):
        return [x[i] / self.norm(x) for i in range(len(x))]

    def project_onto_plane(self, x, n):
        """Project point onto plane defined by normal"""
        d = self.dot_product(x, n) / self.norm(n)
        p = [d * self.normalize(n)[i] for i in range(len(n))]
        return [x[i] - p[i] for i in range(len(x))]
