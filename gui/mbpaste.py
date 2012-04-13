from PySide import QtGui


class MBPaste(QtGui.QGraphicsItemGroup):
    def __init__(self, wld, csize):
        QtGui.QGraphicsItemGroup.__init__(self)
        
        self.world = wld
        self.csize = csize
        self.chunks = {}
        
        self.setZValue(3)

        
    def mousePressEvent(self, event):
        """Records the starting point of a mouse drag on the pasted selection."""
        self.drag_origin = event.scenePos().x(), event.scenePos().y()
        
        
    def mouseMoveEvent(self, event):
        """Moves the pasted selection around the view, in chunk-sized increments."""
        ox, oz = self.drag_origin
        dx, dz = int(event.scenePos().x() - ox), int(event.scenePos().y() - oz)
        mx, mz = 0, 0
        
        if abs(dx) / self.csize:
            mx = dx / self.csize * self.csize
        if abs(dz) / self.csize:
            mz = dz / self.csize * self.csize

        self.setPos(self.pos().x() + mx, self.pos().y() + mz)
        self.drag_origin = ox + mx, oz + mz
        
        
        
