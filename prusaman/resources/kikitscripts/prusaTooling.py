from pcbnew import wxPointMM, FootprintLoad, UTF8
import os


def addPrusaFp(panel, name, position,):
    footprint = FootprintLoad(os.environ["PRUSAMAN_PRUSA_LIB"], name)

    fid = footprint.GetFPID()
    fid.SetLibNickname(UTF8("prusa_other"))
    footprint.SetFPID(fid)

    footprint.SetPosition(position)
    panel.board.Add(footprint)

def addPrusaTooling(panel):
    topLeft, topRight, bottomLeft, bottomRight = panel.panelCorners()
    addPrusaFp(panel, "hole4cutter-2mm", topLeft + wxPointMM(2.5, 2.5))
    addPrusaFp(panel, "hole4cutter-2mm", bottomRight + wxPointMM(-10, -2.5))
    addPrusaFp(panel, "hole4cutter-1,5mm", topRight + wxPointMM(-2.5, 2.5))
    addPrusaFp(panel, "hole4cutter-1,5mm", bottomLeft + wxPointMM(2.5, -2.5))

def kikitPostprocess(panel, args):
    addPrusaTooling(panel)
