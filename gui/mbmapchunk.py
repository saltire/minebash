from PySide import QtGui


class MBMapChunk(QtGui.QGraphicsPixmapItem):
    def __init__(self, tab, (cx, cz), csize):
        QtGui.QGraphicsPixmapItem.__init__(self)
        
        self.setAcceptHoverEvents(1)
        self.setFlag(QtGui.QGraphicsItem.ItemIsSelectable)

        self.tab = tab
        self.coords = cx, cz
        self.csize = csize
        
        
    def hoverMoveEvent(self, event):
        """Update the coordinate labels when hovering on a chunk area."""
        pos = event.scenePos()
        x, z = int(pos.x()), int(pos.y())
        self.tab.update_labels(x, z)
        
        
    def hoverLeaveEvent(self, event):
        """Clears the coordinate labels when leaving a chunk area."""
        self.tab.clear_labels()


    def mousePressEvent(self, event):
        """Sets the selection tools to select or deselect, depending where they click.
        Also handles chunk highlighting if using the brush tool."""
        self.tab.select = True if self.coords not in self.tab.selected else False
        
        if self.tab.win.brush.isChecked():
            self.tab.highlight_chunk(self.coords)
        else:
            event.ignore()

    
    def mouseMoveEvent(self, event):
        """Handles chunk highlighting for the brush tool."""
        pos = event.scenePos()
        x, z = int(pos.x()), int(pos.y())
        cx, cz = x / self.csize, z / self.csize
        self.tab.highlight_chunk((cx, cz))
        
        
    def paint(self, painter, option, widget=None):
        """Modify the colour of a chunk based on whether it is highlighted or selected or not."""
        option.state &= not QtGui.QStyle.State_Selected
        QtGui.QGraphicsPixmapItem.paint(self, painter, option, widget)
        
        if self.tab.paste and self not in self.tab.paste.chunks.values():
            painter.fillRect(self.pixmap().rect(), QtGui.QColor(0, 0, 0, 128))
        else:
            # block is being selected
            if self in self.tab.scene.selectedItems() and self.tab.select and self.coords not in self.tab.selected:
                painter.fillRect(self.pixmap().rect(), QtGui.QColor(0, 255, 0, 128))
            # block is being deselected
            elif self in self.tab.scene.selectedItems() and not self.tab.select and self.coords in self.tab.selected:
                painter.fillRect(self.pixmap().rect(), QtGui.QColor(255, 0, 0, 128))
            # block is already selected
            elif self.coords in self.tab.selected:
                painter.fillRect(self.pixmap().rect(), QtGui.QColor(255, 255, 255, 128))
        
