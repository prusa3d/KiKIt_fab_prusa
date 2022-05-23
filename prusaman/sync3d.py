from __future__ import annotations
import pcbnew
from dataclasses import dataclass

from kikit.eeschema_v6 import extractComponents, getReference

from .project import PrusamanProject
from .bom import PnBFilter

# You might be wondering why so much code for such a simple task? Well, it seems
# that the SWIG API just ignores changes in the original model, so we have to
# rebuild it.

@dataclass
class Vector3d:
    x: float
    y: float
    z: float

    @staticmethod
    def fromVec(v: pcbnew.VECTOR3D) -> Vector3d:
        return Vector3d(v.x, v.y, v.z)

    def toVector(self) -> pcbnew.VECTOR3D:
        v = pcbnew.VECTOR3D()
        v.x = self.x
        v.y = self.y
        v.z = self.z
        return v

@dataclass
class FPModel:
    scale: Vector3d
    rotation: Vector3d
    offset: Vector3d
    opacity: float
    filename: str
    show: bool

    @staticmethod
    def fromModel(m: pcbnew.FP_3DMODEL) -> FPModel:
        return FPModel(
            scale=Vector3d.fromVec(m.m_Scale),
            rotation=Vector3d.fromVec(m.m_Rotation),
            offset=Vector3d.fromVec(m.m_Offset),
            opacity=m.m_Opacity,
            filename=m.m_Filename,
            show=m.m_Show
        )

    def toModel(self) -> pcbnew.FP_3DMODEL:
        m = pcbnew.FP_3DMODEL()
        m.m_Scale = self.scale.toVector()
        m.m_Rotation = self.rotation.toVector()
        m.m_Offset = self.offset.toVector()
        m.m_Opacity = self.opacity
        m.m_Filename = self.filename
        m.m_Show = self.show
        return m


def synchronize3D(board: pcbnew.BOARD) -> None:
    """
    Takes PnB annotation from schematic and applies it to 3D models in the
    board.
    """
    project = PrusamanProject(board.GetFileName())

    bomFilter = PnBFilter()
    bom = extractComponents(str(project.getSchema()))
    visibleRef = set([getReference(x) for x in bom if bomFilter.assemblyFilter(x)])

    for f in board.Footprints():
        visible = f.GetReference() in visibleRef

        # The following code is broken in KiCAD API, let's rebuild the model list
        # for model in f.Models():
        #     print(f"  {model.m_Filename}")
        #     print(f"    {model.m_Show}")
        #     model.m_Show = visible
        #     print(f"    {model.m_Show}")

        models = [FPModel.fromModel(x) for x in f.Models()]
        f.Models().clear()
        for m in models:
            m.show = visible
            f.Add3DModel(m.toModel())

