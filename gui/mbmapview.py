from PySide import QtCore
from PySide import QtGui


class MBMapView(QtGui.QGraphicsView):
    def __init__(self, scene, tab):
        QtGui.QGraphicsView.__init__(self, scene)
        
        self.setRubberBandSelectionMode(QtCore.Qt.ContainsItemShape)

        self.tab = tab
        
        
    def mousePressEvent(self, event):
        """Starts a rubber band if the box tool is selected."""
        self.setDragMode(QtGui.QGraphicsView.RubberBandDrag if self.tab.win.box.isChecked()
                         else QtGui.QGraphicsView.NoDrag)
        QtGui.QGraphicsView.mousePressEvent(self, event)
        
        
    def mouseReleaseEvent(self, event):
        self.tab.update_selection()
