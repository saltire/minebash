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

        filemenu = self.menuBar().addMenu('File')
        open = filemenu.addAction('Open', self.open)
        
        self.tabs = QtGui.QTabWidget(self)
        self.setCentralWidget(self.tabs)
        
        tools = QtGui.QToolBar(self)
        self.addToolBar(tools)
        
        toolgrp = QtGui.QActionGroup(tools)

        self.brush = tools.addAction('Brush')
        self.brush.setCheckable(1)
        toolgrp.addAction(self.brush)
                
        self.box = tools.addAction('Box')
        self.box.setCheckable(1)
        toolgrp.addAction(self.box)
        
        tools.addSeparator()
        
        copy = tools.addAction('Copy')
        copy.triggered.connect(lambda: self.tabs.currentWidget().copy_chunks())
               
        self.pastebtn = tools.addAction('Paste')
        if self.cliptab is None:
            self.pastebtn.setDisabled(1)
        self.pastebtn.triggered.connect(lambda: self.tabs.currentWidget().paste_chunks())
        
        
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
        
        self.chunks = {} # dict of chunks indexed by coords
        self.selected = set() # currently selected chunks in this world
        self.paste = False # whether a pasted, unmerged selection exists in this tab
        
        self.init_ui()
        
        self.draw_map()

        
    def init_ui(self):
        mainlayout = QtGui.QVBoxLayout(self)
        mainlayout.setContentsMargins(10, 10, 10, 10)
        mainlayout.setSpacing(0)

        self.scene = QtGui.QGraphicsScene(self)
        self.scene.setBackgroundBrush(QtGui.QColor(25, 25, 25))
        
        self.view = MBMapView(self.scene, self)
        
        tools = QtGui.QFrame(self)
        info = QtGui.QFrame(self)
        mainlayout.addWidget(self.view)
        mainlayout.addWidget(info)
        mainlayout.addWidget(tools)
        
        # tools row
        
        toolslayout = QtGui.QHBoxLayout(tools)
        toolslayout.setSpacing(10)
        toolslayout.setSizeConstraint(QtGui.QLayout.SetMinimumSize)
        
        tools = QtGui.QButtonGroup()
        
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
        if refresh:
            self.chunks = {}
        
        regions = self.world.get_region_list()
        for rnum, (rx, rz) in enumerate(regions):
            print 'region {0} of {1}:'.format(rnum + 1, len(regions))
            
            for (cx, cz), img in self.get_region_blended_images((rx, rz), refresh).iteritems():
                data = img.tostring('raw', 'BGRA')
                if (cx, cz) not in self.chunks:
                    self.chunks[cx, cz] = MBMapChunk(self, (cx, cz))
                    self.chunks[cx, cz].setPos(cx * world.CSIZE, cz * world.CSIZE)
                    self.scene.addItem(self.chunks[cx, cz])
                self.chunks[cx, cz].setPixmap(QtGui.QPixmap.fromImage(QtGui.QImage(data, world.CSIZE, world.CSIZE, QtGui.QImage.Format_ARGB32)))
                
        if self.paste:
            print 'redrawing pasted chunks'
            
            chunklist = self.paste.chunks.keys()
            regions = world.World(self.paste.wpath).get_region_list(chunklist)
            for rx, rz in regions:
                for (cx, cz), img in self.get_region_blended_images((rx, rz), refresh, chunklist).iteritems():
                    data = img.tostring('raw', 'BGRA')
                    self.paste.chunks[cx, cz].setPixmap(QtGui.QPixmap.fromImage(QtGui.QImage(data, world.CSIZE, world.CSIZE, QtGui.QImage.Format_ARGB32)))
                    
        print 'done.'
        
        
    def get_region_blended_images(self, (rx, rz), refresh=False, whitelist=None):
        imgs = {}
        
        cimgs = self.get_region_chunk_images((rx, rz), 'block', refresh, whitelist)
        if self.biomecheck.isChecked():
            bcimgs = self.get_region_chunk_images((rx, rz), 'biome', refresh, whitelist)
            
        for (rcx, rcz), img in cimgs.iteritems():
            cx, cz = rx * world.RSIZE + rcx, rz * world.RSIZE + rcz
            if self.biomecheck.isChecked():
                imgs[cx, cz] = Image.blend(img, bcimgs[rcx, rcz], 0.5)
            else:
                imgs[cx, cz] = img
                
        return imgs
        
        
    def get_region_chunk_images(self, (rx, rz), type='block', refresh=False, whitelist=None):
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
            
        return {(cx, cz): img.crop((cx * world.CSIZE, cz * world.CSIZE, (cx + 1) * world.CSIZE, (cz + 1) * world.CSIZE))
                for cx, cz in self.world.get_region_chunk_list((rx, rz), whitelist)}
        
        
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
                self.win.pastebtn.setEnabled(1)

                
    def get_clip_chunkmaps(self):
        return {(cx, cz): self.scene.itemAt(cx * world.CSIZE, cz * world.CSIZE).pixmap() for cx, cz in self.selected}
    
    
    def paste_chunks(self):
        if self.win.cliptab is not None:
            self.paste = MBPaste(self.win.cliptab.world.path)
            
            for (cx, cz), chunkmap in self.win.cliptab.get_clip_chunkmaps().iteritems():
                self.paste.chunks[cx, cz] = QtGui.QGraphicsPixmapItem(chunkmap)
                self.paste.chunks[cx, cz].setPos(cx * world.CSIZE, cz * world.CSIZE)
                self.scene.addItem(self.paste.chunks[cx, cz])
                self.paste.addToGroup(self.paste.chunks[cx, cz])
                
            self.scene.addItem(self.paste)
            
            self.view.setViewportUpdateMode(QtGui.QGraphicsView.FullViewportUpdate)
            self.view.ensureVisible(self.paste)
            self.view.setViewportUpdateMode(QtGui.QGraphicsView.MinimalViewportUpdate)
            
            self.scene.update()
            
            
    def highlight_chunk(self, (cx, cz)):
        self.scene.itemAt(cx * world.CSIZE, cz * world.CSIZE).setSelected(1)
        self.selectlabel.setText('Chunks selected: {0}'.format(len(self.selected) if self.selected else ''))

        
    def update_selection(self):
        for chunk in self.scene.selectedItems():
            self.selected.add(chunk.coords) if self.select else self.selected.discard(chunk.coords)
            chunk.setSelected(0)
        self.selectlabel.setText('Chunks selected: {0}'.format(len(self.selected) if self.selected else ''))
        
        
        
class MBPaste(QtGui.QGraphicsItemGroup):
    def __init__(self, wpath):
        QtGui.QGraphicsItemGroup.__init__(self)
        
        self.wpath = wpath
        self.chunks = {}
        
        
    def mousePressEvent(self, event):
        self.drag_origin = event.scenePos().x(), event.scenePos().y()
        
        
    def mouseMoveEvent(self, event):
        ox, oz = self.drag_origin
        dx, dz = int(event.scenePos().x() - ox), int(event.scenePos().y() - oz)
        mx, mz = 0, 0
        
        if abs(dx) / world.CSIZE:
            mx = dx / world.CSIZE * world.CSIZE
        if abs(dz) / world.CSIZE:
            mz = dz / world.CSIZE * world.CSIZE

        self.setPos(self.pos().x() + mx, self.pos().y() + mz)
        self.drag_origin = ox + mx, oz + mz
        
        

class MBMapView(QtGui.QGraphicsView):
    def __init__(self, scene, tab):
        QtGui.QGraphicsView.__init__(self, scene)
        
        self.setRubberBandSelectionMode(QtCore.Qt.ContainsItemShape)

        self.tab = tab
        
        
    def mousePressEvent(self, event):
        self.setDragMode(QtGui.QGraphicsView.RubberBandDrag if self.tab.win.box.isChecked()
                         else QtGui.QGraphicsView.NoDrag)
        QtGui.QGraphicsView.mousePressEvent(self, event)
        
        
    def mouseReleaseEvent(self, event):
        self.tab.update_selection()



class MBMapChunk(QtGui.QGraphicsPixmapItem):
    def __init__(self, tab, (cx, cz)):
        QtGui.QGraphicsPixmapItem.__init__(self)
        
        self.setAcceptHoverEvents(1)
        self.setFlag(QtGui.QGraphicsItem.ItemIsSelectable)

        self.tab = tab
        self.coords = cx, cz
        
        
    def hoverLeaveEvent(self, event):
        self.tab.clear_labels()


    def hoverMoveEvent(self, event):
        pos = event.scenePos()
        x, z = int(pos.x()), int(pos.y())
        self.tab.update_labels(x, z)
        
        
    def mousePressEvent(self, event):
        self.tab.select = True if self.coords not in self.tab.selected else False
        
        if self.tab.win.brush.isChecked():
            self.tab.highlight_chunk(self.coords)
        else:
            event.ignore()

    
    def mouseMoveEvent(self, event):
        pos = event.scenePos()
        x, z = int(pos.x()), int(pos.y())
        cx, cz = x / world.CSIZE, z / world.CSIZE
        self.tab.highlight_chunk((cx, cz))
        
        
    def paint(self, painter, option, widget=None):
        option.state &= not QtGui.QStyle.State_Selected
        QtGui.QGraphicsPixmapItem.paint(self, painter, option, widget)
        
        if self.tab.paste:
            painter.fillRect(self.pixmap().rect(), QtGui.QColor(0, 0, 0, 128))
        else:
            if self.coords in self.tab.selected:
                painter.fillRect(self.pixmap().rect(), QtGui.QColor(255, 255, 255, 128))
            if self in self.tab.scene.selectedItems():
                painter.fillRect(self.pixmap().rect(), QtGui.QColor(255, 0, 0, 128))
        
    
        
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


