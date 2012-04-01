import argparse
import os
import sys

from PySide import QtCore
from PySide import QtGui
from PIL import Image

from minebash import orthomap
from minebash import world


class MineBash(QtGui.QMainWindow):
    def __init__(self, wpath=None, colours=None, biomes=None):
        QtGui.QMainWindow.__init__(self)
        
        self.colours = colours
        self.biomes = biomes
        
        self.cliptab = None
        
        self.init_ui()
        self.show()
        
        if wpath:
            startworld = world.World(wpath)
            tab = MBWorldTab(self, startworld)
            self.tabs.addTab(tab, startworld.name)
        
        
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
        self.map = orthomap.OrthoMap(self.world, self.win.colours, self.win.biomes)
        
        self.selected = set()
        self.paint = None
        
        self.init_ui()
        
        self.draw_map()

        
    def init_ui(self):
        mainlayout = QtGui.QVBoxLayout(self)
        mainlayout.setContentsMargins(10, 10, 10, 10)
        mainlayout.setSpacing(0)

        self.scene = QtGui.QGraphicsScene(self)
        self.scene.setBackgroundBrush(QtGui.QColor(25, 25, 25))
        view = QtGui.QGraphicsView(self.scene, self)
        tools = QtGui.QFrame(self)
        info = QtGui.QFrame(self)
        mainlayout.addWidget(view)
        mainlayout.addWidget(info)
        mainlayout.addWidget(tools)
        
        # tools row
        
        toolslayout = QtGui.QHBoxLayout(tools)
        toolslayout.setSpacing(10)
        toolslayout.setSizeConstraint(QtGui.QLayout.SetMinimumSize)
        
        self.copy = QtGui.QPushButton('Copy', self)
        self.copy.clicked.connect(self.copy_chunks)
        toolslayout.addWidget(self.copy)
        
        self.paste = QtGui.QPushButton('Paste', self)
        self.paste.clicked.connect(self.paste_chunks)
        if self.win.cliptab is None:
            self.paste.setDisabled(1)
        toolslayout.addWidget(self.paste)
        
        self.copylabel = QtGui.QLabel('')
        toolslayout.addWidget(self.copylabel)
        
        toolslayout.addStretch()
        
        generate = QtGui.QPushButton('Generate', self)
        generate.clicked.connect(lambda: self.draw_map(refresh=1))
        toolslayout.addWidget(generate)
        
        # info row
        
        infolayout = QtGui.QHBoxLayout(info)
        infolayout.setSpacing(10)
        infolayout.setSizeConstraint(QtGui.QLayout.SetMinimumSize)

        self.labels = {}
        for label in ('Region', 'Chunk', 'Block'):
            self.labels[label] = QtGui.QLabel('{0}:'.format(label))
            self.labels[label].setMinimumSize(100, 30)
            infolayout.addWidget(self.labels[label])
            
        self.selectlabel = QtGui.QLabel('Chunks selected:')
        self.selectlabel.setMinimumSize(100, 30)
        infolayout.addWidget(self.selectlabel)
        
        infolayout.addStretch()
        
        self.biomecheck = QtGui.QCheckBox('Show biomes')
        self.biomecheck.setMinimumSize(80, 30)
        self.biomecheck.stateChanged.connect(lambda: self.draw_map())
        infolayout.addWidget(self.biomecheck)

        
    def draw_map(self, refresh=False):
        regions = self.world.get_region_list()
        for rnum, (rx, rz) in enumerate(regions):
            print 'region {0} of {1}:'.format(rnum + 1, len(regions))
            img = self.get_region_image((rx, rz), refresh=refresh)
                
            if self.biomecheck.isChecked():
                bimg = self.get_region_image((rx, rz), type='biome', refresh=refresh)
                img = Image.blend(img, bimg, 0.5)
            
            w, h = img.size
            data = img.tostring('raw', 'BGRA')
            
            pixitem = MBMapRegion(self)
            pixitem.setPixmap(QtGui.QPixmap.fromImage(QtGui.QImage(data, w, h, QtGui.QImage.Format_ARGB32)))
            pixitem.setPos(rx * 512, rz * 512)
            self.scene.addItem(pixitem)
            
        print 'done.'
        
        
    def get_region_image(self, (rx, rz), type='block', refresh=False):
        if type not in ('block', 'biome', 'height'):
            type = 'block'
            
        cachepath = os.path.join(os.getcwd(), 'cache', self.world.name)
        if not os.path.exists(cachepath):
            os.makedirs(cachepath)
            
        path = os.path.join(cachepath, '{0}_{1}.{2}.png'.format(type, rx, rz))
        if os.path.exists(path) and not refresh:
            img = Image.open(path)
            print 'found', path
        else:
            print 'preparing to draw {0} map at region {1}'.format(type, (rx, rz))
            img = self.map.draw_region((rx, rz), type)
            img.save(path)
            print 'cached', path
            
        return img
        
        
    def toggle_select(self, (cx, cz)):
        if (cx, cz) in self.selected and self.paint != 1:
            self.scene.removeItem(self.scene.itemAt(cx * world.CSIZE, cz * world.CSIZE))
            self.selected.remove((cx, cz))
            self.paint = 0
            
        elif (cx, cz) not in self.selected and self.paint != 0:
            sq = QtGui.QGraphicsRectItem(cx * world.CSIZE, cz * world.CSIZE, world.CSIZE, world.CSIZE)
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
        cx, cz = x / world.CSIZE, z / world.CSIZE
        rx, rz = cx / world.CSIZE, cz / world.CSIZE
        self.labels['Block'].setText('Block: {0}, {1}'.format(x, z))
        self.labels['Chunk'].setText('Chunk: {0}, {1}'.format(cx, cz))
        self.labels['Region'].setText('Region: {0}, {1}'.format(rx, rz))
        
        
    def copy_chunks(self):
        if self.selected:
            self.win.cliptab = self
            self.copylabel.setText('{0} chunks copied'.format(len(self.selected)))
            
            # enable paste buttons
            for index in range(self.win.tabs.count()):
                self.win.tabs.widget(index).paste.setEnabled(1)

                
    def get_clip_chunks(self):
        chunks = {}
        
        if self.selected:
            cxmin = min(cx for cx, cz in self.selected)
            cxmax = max(cx for cx, cz in self.selected)
            czmin = min(cz for cx, cz in self.selected)
            czmax = max(cz for cx, cz in self.selected)
            w = (cxmax + 1 - cxmin) * world.CSIZE
            h = (czmax + 1 - czmin) * world.CSIZE
            
            brsize = world.CSIZE * world.RSIZE
            
            for cx, cz in self.selected:
                bx, bz = cx * world.CSIZE, cz * world.CSIZE
                regionmap = self.scene.items(bx, bz, world.CSIZE, world.CSIZE)[-1].pixmap()
                chunkmap = regionmap.copy(bx % brsize, bz % brsize, world.CSIZE, world.CSIZE)
                chunks[cx, cz] = QtGui.QGraphicsPixmapItem(chunkmap)
            
        return chunks
            
            
    def paste_chunks(self):
        if self.win.cliptab is not None:
            clip = QtGui.QGraphicsItemGroup()
            
            for (cx, cz), chunk in self.win.cliptab.get_clip_chunks().items():
                chunk.setPos(cx * world.CSIZE, cz * world.CSIZE)
                clip.addToGroup(chunk)
                self.scene.addItem(chunk)
        
        
        
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
        cx, cz = x / world.CSIZE, z / world.CSIZE
        if (cx, cz) in self.tab.world.chunklist and self.tab.paint is not None:
            self.tab.toggle_select((cx, cz))
        
        
    def mousePressEvent(self, event):
        pos = event.scenePos()
        x, z = int(pos.x()), int(pos.y())
        cx, cz = x / world.CSIZE, z / world.CSIZE
        self.tab.toggle_select((cx, cz))
        
    
    def mouseReleaseEvent(self, event):
        self.tab.paint = None


        
# startup

if __name__ == '__main__':
    argp = argparse.ArgumentParser('Mine Bash - a Minecraft map editor.')
    argp.add_argument('--world', '-w')
    argp.add_argument('--colours', '-c')
    argp.add_argument('--biomes', '-b')
    
    args = argp.parse_args()
    
    wpath = args.world or 'd:\\games\\Minecraft\\server\\loreland' # temp default
    
    app = QtGui.QApplication(sys.argv)

    minebash = MineBash(wpath, args.colours, args.biomes)

    sys.exit(app.exec_())


