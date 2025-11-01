"""
UVV Zen Cluster
Advanced UV island representation with vertex/edge/face management
"""

from .base_elements import UvEdge, UvFace, UvVertex
from ..generic_helpers import Scope, Distortion
from .base_cluster import BaseCluster
from ..constants import u_axis


class CheckerZcluster:
    """Checks and fixes broken UV borders"""

    def chk_broken_borders_v_01(self):
        safe_loops = range(10)
        for c in safe_loops:
            b_verts = self.get_bound_verts()
            scope = Scope()
            for vert in b_verts:
                scope.append(vert.uv_co, vert)

            ids_scope = []
            for i, ve in scope.data.items():
                if len(ve) > 2:
                    ids_scope.append(list({v.index for v in ve}))

            if ids_scope:
                for ids in ids_scope:
                    if len(ids) == 1:
                        id = ids[0]
                        vert = self.uv_verts[id]
                        for i in range(len(vert.link_loops) - 1):
                            new_vert = UvVertex(
                                len(self.uv_verts) + 1,
                                vert.mesh_vert,
                                [vert.link_loops.pop(), ],
                                vert.uv_layer
                                )
                            new_vert.move_by(Distortion.get_vector_2d(0.0001))
                            self.uv_verts.append(new_vert)
            else:
                return True
            self.coo_deps = {}
            self._collect_uv_verts()
            self._collect_uv_edges()
        return False

    def douplicate_uv_vertex(self, in_vertex):
        new_vert = UvVertex(
            len(self.uv_verts) + 1,
            in_vertex.mesh_vert,
            [in_vertex.link_loops.pop(), ],
            in_vertex.uv_layer
            )
        self.uv_verts.append(new_vert)
        return new_vert

    def chk_broken_borders(self):
        safe_loops = range(10)
        for c in safe_loops:
            b_verts = self.get_bound_verts()
            scope = Scope()
            for vert in b_verts:
                scope.append(vert.uv_co, vert)

            ids_scope = []
            for i, ve in scope.data.items():
                if len(ve) > 2:
                    ids_scope.append(list({v.index for v in ve})[0])
        return ids_scope

    def fix_broken_borders(self):
        bborders = self.chk_broken_borders()
        if not bborders:
            return True
        sorter = {}
        verts = [self.uv_verts[i] for i in bborders]

        for v in verts:
            sorter.update({v: []})
            faces = [f for f in v.link_uv_faces]
            full_set = []
            while faces:
                start_f = faces.pop()
                sub_set = [start_f, ]
                es1 = set(e.index for e in start_f.mesh_face.edges)
                i = len(faces)
                while i:
                    i -= 1
                    es2 = set(e.index for e in faces[i].mesh_face.edges)
                    if es1.intersection(es2):
                        sub_set.append(faces[i])
                        del faces[i]
                sorter[v].append(sub_set)
        counter = 0
        for vert, full_set in sorter.items():
            for i in range(1, len(full_set)):
                n_vert = self.douplicate_uv_vertex(vert)
                n_vert.link_uv_faces = full_set[i]
                n_vert_loops = set([loop for uv_face in n_vert.link_uv_faces for loop in uv_face.mesh_face.loops])
                vert_loops = set(vert.link_loops)
                intersection = vert_loops.intersection(n_vert_loops)
                n_vert.link_loops = list(intersection)
                n_vert.move_by(Distortion.get_vector_2d(0.0001))
                counter += 1

        return True

    def check_multiple_loops(self):
        return [edge.index for edge in {e for f in self.island for e in f.edges} if len(edge.link_loops) > 2]


class ZenCluster(BaseCluster, CheckerZcluster):
    """Advanced UV island representation with automatic fixing"""

    def __init__(self, context, obj, island, bm=None) -> None:
        super().__init__(context, obj, island, bm)
        self.init_cycles = 0
        self.broken_borders_passed = False
        self.same_uv_verts_coords_passed = False
        self.init_zen_cluster()

    def init_zen_cluster(self):
        self.coo_deps = dict()
        self.mult = 1000
        self.init_cycles += 1

        self.uv_verts = []
        self.uv_faces = []
        self.uv_edges = []

        self._collect_uv_verts()
        self._collect_uv_faces()
        self._collect_uv_edges()

        self.check_consistency()

    def deselect_all_edges(self):
        for edge in self.uv_edges:
            edge.select(self.context, state=False)

    def get_edges_by_orientation(self, _dir=u_axis):
        return [edge for edge in self.uv_edges if edge.get_orientation() == _dir]

    def get_edges_by_angle_to_axis(self, angle, axis=u_axis):
        return [edge for edge in self.uv_edges if edge.get_orientation_by_angle(angle, axis)]

    def check_consistency(self):
        if not self.broken_borders_passed:
            self.broken_borders_passed = self.fix_broken_borders()
        if not self.same_uv_verts_coords_passed:
            if self._check_same_uv_vert_coords():
                self.same_uv_verts_coords_passed = True
                self.create_coo_dependency()
                self.init_zen_cluster()

    def update_uv_verts(self):
        for v in self.uv_verts:
            v.update_uv_co()

    def is_template(self):
        """Check if cluster is template (all UVs at zero)"""
        return len(self.uv_verts) <= 1 and len(self.island) > 0

    def _collect_uv_verts(self):
        self.uv_verts.clear()
        self.create_coo_dependency()
        idx = 0
        for coo, vert in self.coo_deps.items():
            uv_vertex = UvVertex(idx, vert["mesh_vert"], vert["link_loops"], self.uv_layer)
            self.coo_deps[coo].update({"uv_vert": uv_vertex})
            idx += 1
            self.uv_verts.append(uv_vertex)

    def _check_same_uv_vert_coords(self):
        scope = Scope()
        for v in self.uv_verts:
            scope.append(v.uv_co, v)
        for uv_vert in scope.get_mults_values():
            uv_vert.move_by(Distortion.get_vector_2d(size=0.01))
        return True

    def create_coo_dependency(self):
        self.coo_deps.clear()
        vcl = list(self.loops.values())
        for loop in vcl:
            mv_index = loop.vert.index
            coo = (loop[self.uv_layer].uv * self.mult).copy().freeze()
            key = (coo, mv_index)
            if key not in self.coo_deps.keys():
                self.coo_deps.update({key: {"link_loops": [loop], "mesh_vert": loop.vert, "uv_co": key[0]}})
            else:
                self.coo_deps[key]["link_loops"].append(loop)

    def _collect_uv_faces(self):
        self.uv_faces.clear()
        for idx, face in enumerate(self.island):
            uv_face = UvFace(idx, face)
            for loop in face.loops:
                coo = (loop[self.uv_layer].uv * self.mult).copy().freeze()
                mv_index = loop.vert.index
                key = (coo, mv_index)
                uv_face.uv_verts.append(self.coo_deps[key]["uv_vert"])
            for uv_vert in uv_face.uv_verts:
                uv_vert.link_uv_faces.append(uv_face)
            self.uv_faces.append(uv_face)

    def _collect_uv_edges(self):
        self.uv_edges.clear()
        if self.uv_verts:
            index = 0
            loops_scope = list(self.loops.values())
            while loops_scope:
                loop = loops_scope[0]
                prev_loops = [lp for lp in loop.edge.link_loops if lp.index in self.loops.keys()]

                l1 = (loop[self.uv_layer].uv * self.mult).copy().freeze()
                l1_mv_iindex = loop.vert.index
                key1 = (l1, l1_mv_iindex)
                l2 = (loop.link_loop_next[self.uv_layer].uv * self.mult).copy().freeze()
                l2_mv_iindex = loop.link_loop_next.vert.index
                key2 = (l2, l2_mv_iindex)
                loops = []
                for lp in prev_loops:
                    loop_co = lp[self.uv_layer]
                    next_loop_co = lp.link_loop_next[self.uv_layer]

                    if loop_co.uv * self.mult in [l1, l2] and next_loop_co.uv * self.mult in [l1, l2]:
                        loops.append(lp)
                        loops_scope.remove(lp)

                vert_01 = self.coo_deps[key1]["uv_vert"]
                vert_02 = self.coo_deps[key2]["uv_vert"]

                self.uv_edges.append(UvEdge(index, loop.edge, loops, vert_01, vert_02, self.uv_layer))
                index += 1

    def get_bound_edges(self):
        boundary = [e for e in self.uv_edges if len(e.loops) == 1]
        return boundary

    def get_selected_edges(self):
        return [e for e in self.uv_edges if e.get_select_state(self.context)]

    def get_bound_verts(self):
        return [v for e in self.get_bound_edges() for v in e.verts]

    def append_uv_edge(self, uv_edge):
        uv_edge.index = len(self.uv_edges) + 1
        if isinstance(uv_edge, UvEdge):
            self.uv_edges.append(uv_edge)
