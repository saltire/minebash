import os
import sys

from PySide import QtCore
from PySide import QtGui
from PIL import Image

from minebash import orthomap
from minebash import world


class MineBash(QtGui.QMainWindow):
    def __init__(self, colours, wld):
        QtGui.QMainWindow.__init__(self)
        
        self.colours = colours
        
        self.init_ui()
        self.show()
        
        # temp
        tab = MBWorldTab(self, wld)
        self.tabs.addTab(tab, wld.name)
        
        
    def init_ui(self):
        self.resize(800, 700)
        self.setContentsMargins(10, 10, 10, 10)
        self.setWindowTitle('Mine Bash')

        self.tabs = QtGui.QTabWidget(self)
        self.setCentralWidget(self.tabs)
        
        filemenu = self.menuBar().addMenu('File')
        open = filemenu.addAction('Open')
        open.triggered.connect(self.open)
        
        
    def open(self):
        dir = QtGui.QFileDialog.getExistingDirectory()
        if os.path.exists(os.path.join(dir, 'level.dat')):
            tab = MBWorldTab(self, world.World(dir))
            self.tabs.addTab(tab, tab.world.name)
            self.tabs.setCurrentWidget(tab)
            
        else:
            print 'Not a world dir!'
        
        

class MBWorldTab(QtGui.QWidget):
    def __init__(self, win, wld):
        QtGui.QWidget.__init__(self)
        
        self.win = win
        self.world = wld
        
        self.selected = set()
        self.paint = None
        
        self.init_ui()
        
        self.draw_map()

        
    def init_ui(self):
        mainlayout = QtGui.QVBoxLayout(self)
        mainlayout.setContentsMargins(10, 10, 10, 10)
        mainlayout.setSpacing(10)

        self.scene = QtGui.QGraphicsScene(self)
        self.scene.setBackgroundBrush(QtGui.QColor(25, 25, 25))
        view = QtGui.QGraphicsView(self.scene, self)
        frame = QtGui.QFrame(self)
        
        mainlayout.addWidget(view)
        mainlayout.addWidget(frame)
        
        framelayout = QtGui.QHBoxLayout(frame)
        framelayout.setSpacing(10)
        framelayout.setSizeConstraint(QtGui.QLayout.SetMinimumSize)

        self.labels = {}
        for label in ('Region', 'Chunk', 'Block'):
            self.labels[label] = QtGui.QLabel('{0}:'.format(label))
            self.labels[label].setMinimumSize(80, 40)
            framelayout.addWidget(self.labels[label])
            
        self.selectlabel = QtGui.QLabel('Chunks selected:')
        framelayout.addWidget(self.selectlabel)
        
        framelayout.addStretch()

        generate = QtGui.QPushButton('Generate', self)
        generate.clicked.connect(lambda: self.draw_map(1))
        framelayout.addWidget(generate)
        
        
    def draw_map(self, refresh=0):
        cachepath = os.path.join(os.getcwd(), 'cache', self.world.name)
        if not os.path.exists(cachepath):
            os.makedirs(cachepath)
            
        regions = self.world.get_region_list()
        for rnum, (rx, rz) in enumerate(regions):
            
            path = os.path.join(cachepath, '{0}.{1}.png'.format(rx, rz))
            print 'trying region {0}/{1} at {2}...'.format(rnum + 1, len(regions), path),
            if os.path.exists(path) and not refresh:
                img = Image.open(path)
                print 'found.'
            else:
                print 'nope.'
                img = orthomap.OrthoMap(self.world, self.win.colours).draw_region((rx, rz))
                img.save(path)
                print 'cached', path
                
            w, h = img.size
            data = img.tostring('raw', 'BGRA')
            
            pixitem = MBMapRegion(self)
            pixitem.setPixmap(QtGui.QPixmap.fromImage(QtGui.QImage(data, w, h, QtGui.QImage.Format_ARGB32)))
            pixitem.setPos(rx * 512, rz * 512)
            self.scene.addItem(pixitem)
            
        print 'done.'
        
        
    def toggle_select(self, (cx, cz)):
        csize = self.world.csize
        
        if (cx, cz) in self.selected and self.paint != 1:
            self.scene.removeItem(self.scene.itemAt(cx * csize, cz * csize))
            self.selected.remove((cx, cz))
            self.paint = 0
            
        elif (cx, cz) not in self.selected and self.paint != 0:
            sq = QtGui.QGraphicsRectItem(cx * csize, cz * csize, csize, csize)
            pen = QtGui.QPen()
            pen.setStyle(QtCore.Qt.NoPen)
            sq.setPen(pen)
            sq.setBrush(QtGui.QColor(255, 255, 255, 128))
            self.scene.addItem(sq)
            self.selected.add((cx, cz))
            self.paint = 1
            
        self.selectlabel.setText('Chunks selected: {0}'.format(len(self.selected) if self.selected else ''))

        
    def clear_labels(self):
        for text, label in self.labels.items():
            label.setText('{0}:'.format(text))
        
        
    def update_labels(self, x, z):
        cx, cz = x / self.world.csize, z / self.world.csize
        rx, rz = cx / self.world.rsize, cz / self.world.rsize
        self.labels['Block'].setText('Block: {0}, {1}'.format(x, z))
        self.labels['Chunk'].setText('Chunk: {0}, {1}'.format(cx, cz))
        self.labels['Region'].setText('Region: {0}, {1}'.format(rx, rz))
        
        
        
class MBMapRegion(QtGui.QGraphicsPixmapItem):
    def __init__(self, tab):
        QtGui.QGraphicsPixmapItem.__init__(self)

        self.setAcceptHoverEvents(1)
        self.tab = tab
        
        
    def hoverLeaveEvent(self, event):
        self.tab.clear_labels()


    def hoverMoveEvent(self, event):
        pos = event.scenePos()
        x, z = int(pos.x()), int(pos.y())
        self.tab.update_labels(x, z)
        
    
    def mouseMoveEvent(self, event):
        pos = event.scenePos()
        x, z = int(pos.x()), int(pos.y())
        cx, cz = x / self.tab.world.csize, z / self.tab.world.csize
        if (cx, cz) in self.tab.world.chunklist and self.tab.paint is not None:
            self.tab.toggle_select((cx, cz))
        
        
    def mousePressEvent(self, event):
        pos = event.scenePos()
        x, z = int(pos.x()), int(pos.y())
        cx, cz = x / self.tab.world.csize, z / self.tab.world.csize
        self.tab.toggle_select((cx, cz))
        
    
    def mouseReleaseEvent(self, event):
        self.tab.paint = None


        
# startup

wpath = 'd:\\games\\Minecraft\\server\\loreland'
colours = 'colours.csv'

app = QtGui.QApplication(sys.argv)

minebash = MineBash(colours, world.World(wpath))

sys.exit(app.exec_())


