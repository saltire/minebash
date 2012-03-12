import os
import sys

from PySide import QtGui
from PIL import Image

from minebash import orthomap
from minebash import world


class MineBash(QtGui.QWidget):
    def __init__(self, wld, colours):
        QtGui.QWidget.__init__(self)
        
        self.world = wld
        self.colours = colours
        
        self.init_ui()
        
        self.draw_map()
        
        
    def init_ui(self):
        self.resize(800, 700)
        self.setWindowTitle('Mine Bash')
        self.show()

        self.scene = QtGui.QGraphicsScene(self)
        view = QtGui.QGraphicsView(self.scene, self)
        frame = QtGui.QFrame(self)
        
        mainlayout = QtGui.QVBoxLayout(self)
        mainlayout.setContentsMargins(20, 20, 20, 20)
        mainlayout.setSpacing(20)
        mainlayout.addWidget(view)
        mainlayout.addWidget(frame)
        
        framelayout = QtGui.QHBoxLayout(frame)
        framelayout.setSpacing(20)
        framelayout.setSizeConstraint(QtGui.QLayout.SetMinimumSize)

        self.labels = {}
        for label in ('Region', 'Chunk', 'Block'):
            self.labels[label] = QtGui.QLabel('')
            self.labels[label].setMinimumSize(80, 40)
            framelayout.addWidget(self.labels[label])
        
        generate = QtGui.QPushButton('Generate', self)
        generate.clicked.connect(lambda: self.draw_map(1))
        
        framelayout.addStretch()
        framelayout.addWidget(generate)
        
        
    def draw_map(self, refresh=0):
        regions = self.world.get_region_list()
        for rnum, (rx, rz) in enumerate(regions):
            path = os.path.join('cache', '{0}.{1}.png'.format(rx, rz))
            print 'trying region {0}/{1} at {2}...'.format(rnum + 1, len(regions), path),
            if os.path.exists(path) and not refresh:
                img = Image.open(path)
                print 'found.'
            else:
                print 'nope.'
                img = orthomap.OrthoMap(self.world, self.colours).draw_region((rx, rz))
                img.save(path)
                print 'cached', path
                
            w, h = img.size
            data = img.tostring('raw', 'BGRA')
            
            pixitem = MBMapRegion(self)
            pixitem.setPixmap(QtGui.QPixmap.fromImage(QtGui.QImage(data, w, h, QtGui.QImage.Format_ARGB32)))
            pixitem.setPos(rx * 512, rz * 512)
            self.scene.addItem(pixitem)
            
        print 'done.'
        
        
    def clear_labels(self):
        for label in self.labels.values():
            label.setText('')
        
        
    def update_labels(self, x, z):
        cx, cz = x / self.world.csize, z / self.world.csize
        rx, rz = cx / self.world.rsize, cz / self.world.rsize
        self.labels['Block'].setText('Block: {0}, {1}'.format(x, z))
        self.labels['Chunk'].setText('Chunk: {0}, {1}'.format(cx, cz))
        self.labels['Region'].setText('Region: {0}, {1}'.format(rx, rz))
        

        
        
class MBMapRegion(QtGui.QGraphicsPixmapItem):
    def __init__(self, win):
        QtGui.QGraphicsPixmapItem.__init__(self)

        self.setAcceptHoverEvents(1)
        self.win = win
        self.csize = 16
        self.rsize = 32
        
        
    def hoverLeaveEvent(self, event):
        self.win.clear_labels()


    def hoverMoveEvent(self, event):
        pos = event.scenePos()
        x, z = int(pos.x()), int(pos.y())
        self.win.update_labels(x, z)
        
        

        
# startup

wpath = 'd:\\games\\Minecraft\\server\\loreland'
colours = 'colours.csv'

app = QtGui.QApplication(sys.argv)

minebash = MineBash(world.World(wpath), colours)

sys.exit(app.exec_())


