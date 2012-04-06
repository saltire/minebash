import argparse
import os
import sys

from PySide import QtCore
from PySide import QtGui
from PIL import Image

from minebash import orthomap
from minebash import world


class MineBash(QtGui.QMainWindow):
    def __init__(self, wpaths=None, colours=None, biomes=None):
        QtGui.QMainWindow.__init__(self)
        
        self.colours = colours
        self.biomes = biomes
        
        self.cliptab = None # the tab chunks have been copied from
        
        self.init_ui()
        self.show()
        
        if wpaths:
            for wpath in wpaths.split(','):
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
        self.tabs.currentChanged.connect(self.update_toolbar)
        
        tools = QtGui.QToolBar(self)
        self.addToolBar(tools)
        
        # selection tools
        
        self.toolgrp = QtGui.QActionGroup(tools)

        self.brush = tools.addAction('Brush')
        self.brush.setCheckable(1)
        self.toolgrp.addAction(self.brush)
                
        self.box = tools.addAction('Box')
        self.box.setCheckable(1)
        self.toolgrp.addAction(self.box)
        
        # clipboard tools
        
        tools.addSeparator()
        
        self.copybtn = tools.addAction('Copy')
        self.copybtn.triggered.connect(lambda: self.tabs.currentWidget().copy_chunks())
               
        self.pastebtn = tools.addAction('Paste')
        if self.cliptab is None:
            self.pastebtn.setDisabled(1)
        self.pastebtn.triggered.connect(lambda: self.tabs.currentWidget().paste_chunks())
        
        self.mergebtn = tools.addAction('Merge')
        self.mergebtn.setDisabled(1)
        self.mergebtn.triggered.connect(lambda: self.tabs.currentWidget().merge_chunks())
        
        self.cancelbtn = tools.addAction('Cancel Merge')
        self.cancelbtn.setDisabled(1)
        self.cancelbtn.triggered.connect(lambda: self.tabs.currentWidget().cancel_merge())
        
        # status bar
        
        self.status = self.statusBar()
        self.status.setSizeGripEnabled(0)
        self.status.setContentsMargins(10, 0, 10, 0)
        
        self.copylabel = QtGui.QLabel('')
        self.status.addWidget(self.copylabel)
    

    def open(self):
        """Open a file dialog and return a world path."""
        dir = QtGui.QFileDialog.getExistingDirectory()
        if os.path.exists(os.path.join(dir, 'level.dat')):
            tab = MBWorldTab(self, world.World(dir))
            self.tabs.addTab(tab, tab.world.name)
            self.tabs.setCurrentWidget(tab)
            
        else:
            print 'Not a world dir!'
    
    
    def update_toolbar(self):
        """On switching to a new tab, enables and disables tools in the toolbar."""
        tab = self.tabs.currentWidget()
        
        self.toolgrp.setDisabled(1 if tab.paste else 0)
        self.copybtn.setEnabled(1 if tab.selected else 0)
        self.pastebtn.setEnabled(1 if self.cliptab and not tab.paste else 0)
        self.mergebtn.setEnabled(1 if tab.paste else 0)
        self.cancelbtn.setEnabled(1 if tab.paste else 0)
            
            

class MBWorldTab(QtGui.QWidget):
    def __init__(self, win, wld):
        QtGui.QWidget.__init__(self)
        
        self.win = win
        self.world = wld
        
        self.chunks = {} # dict of chunks indexed by coords
        self.selected = set() # currently selected chunks in this world
        self.copied = set() # last copied chunks in this world
        self.select = True # whether tools will select or deselect chunks
        self.paste = None # a pasted, unmerged selection of chunks
        self.merged = {} # dict of merged chunk info
        
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
        
        self.pastelabel = QtGui.QLabel('')
        toolslayout.addWidget(self.pastelabel)
        
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
        """Gets images of all the chunks in the current tab's world, as well as any pasted in,
         and adds their pixmaps to the view."""
         
        # discard chunk list, as we will be reading fresh from the world file
        if refresh:
            self.chunks = {}
        
        # redraw all chunks on the map (regenerating image cache if specified)
        regions = self.world.get_region_list()
        for rnum, (rx, rz) in enumerate(regions):
            print 'region {0} of {1}:'.format(rnum + 1, len(regions))
            
            for (cx, cz), img in self.get_region_chunk_images(self.world, (rx, rz), refresh).iteritems():
                data = img.tostring('raw', 'BGRA')
                if (cx, cz) not in self.chunks:
                    self.chunks[cx, cz] = MBMapChunk(self, (cx, cz))
                    self.chunks[cx, cz].setPos(cx * world.CSIZE, cz * world.CSIZE)
                    self.scene.addItem(self.chunks[cx, cz])
                self.chunks[cx, cz].setPixmap(QtGui.QPixmap.fromImage(QtGui.QImage(data, world.CSIZE, world.CSIZE, QtGui.QImage.Format_ARGB32)))
            
        # redraw pasted selection, if any
        if self.paste:
            print 'redrawing pasted chunks from', self.paste.wpath
            
            pworld = world.World(self.paste.wpath)
            chunklist = self.paste.chunks.keys()
            for rx, rz in pworld.get_region_list(chunklist):
                for (cx, cz), img in self.get_region_chunk_images(pworld, (rx, rz), refresh, chunklist).iteritems():
                    data = img.tostring('raw', 'BGRA')
                    self.paste.chunks[cx, cz].setPixmap(QtGui.QPixmap.fromImage(QtGui.QImage(data, world.CSIZE, world.CSIZE, QtGui.QImage.Format_ARGB32)))
                    
        print 'done.'
        
        
    def get_region_chunk_images(self, wld, (rx, rz), refresh=False, whitelist=None):
        """Gets an image of a region and chops it into images of all chunks in the region.
        Optionally adds a biome overlay first."""
        img = self.get_region_image(wld, (rx, rz), 'block', refresh)
        if self.biomecheck.isChecked():
            img = Image.blend(img, self.get_region_image(wld, (rx, rz), 'biome', refresh), 0.5)
            
        return {(rx * world.RSIZE + cx, rz * world.RSIZE + cz):
                    img.crop((cx * world.CSIZE, cz * world.CSIZE, (cx + 1) * world.CSIZE, (cz + 1) * world.CSIZE))
                for cx, cz in wld.get_region_chunk_list((rx, rz), whitelist)}
    
    
    def get_region_image(self, wld, (rx, rz), type='block', refresh=False, whitelist=None):
        """Returns an image of a region. Will use cached images if available, unless refresh specified.
        Caches images in a subdirectory for the current world."""
        if type not in ('block', 'biome', 'height'):
            type = 'block'
        
        cachepath = os.path.join(os.getcwd(), 'cache', wld.name)
        if not os.path.exists(cachepath):
            os.makedirs(cachepath)
        path = os.path.join(cachepath, '{0}_{1}.{2}.png'.format(type, rx, rz))
        
        if os.path.exists(path) and not refresh:
            # use cached region image
            img = Image.open(path)
            print 'found', path
        else:
            # draw a new region image and cache it
            print 'preparing to draw {0} map at region {1}'.format(type, (rx, rz))
            img = orthomap.OrthoMap(wld, self.win.colours, self.win.biomes).draw_region((rx, rz), type)
            img.save(path)
            print 'cached', path

        return img
        
        
    def clear_labels(self):
        """Clears the coordinate labels."""
        for text, label in self.labels.items():
            label.setText('{0}:'.format(text))
        
        
    def update_labels(self, x, z):
        """Updates coordinate labels with the region, chunk, and block under the mouse cursor."""
        cx, cz = x / world.CSIZE, z / world.CSIZE
        rx, rz = cx / world.CSIZE, cz / world.CSIZE
        self.labels['Block'].setText('Block: {0}, {1}'.format(x, z))
        self.labels['Chunk'].setText('Chunk: {0}, {1}'.format(cx, cz))
        self.labels['Region'].setText('Region: {0}, {1}'.format(rx, rz))
            
            
    def highlight_chunk(self, (cx, cz)):
        """Mark a chunk to be highlighted by a selection tool."""
        if (cx, cz) in self.chunks:
            self.scene.itemAt(cx * world.CSIZE, cz * world.CSIZE).setSelected(1)

        
    def update_selection(self):
        """Adds or removes all highlighted chunks from the selection."""
        for chunk in self.scene.selectedItems():
            self.selected.add(chunk.coords) if self.select else self.selected.discard(chunk.coords)
            chunk.setSelected(0)
        self.selectlabel.setText('Chunks selected: {0}'.format(len(self.selected) if self.selected else ''))
        self.win.copybtn.setEnabled(1 if self.selected else 0)
        
        
    def copy_chunks(self):
        """Sets this tab as the current tab to copy from, and enables the paste tool."""
        if self.selected:
            self.win.cliptab = self
            self.copied = self.selected.copy()
            self.win.pastebtn.setEnabled(1)
            
            self.win.copylabel.setText('{0} chunks copied from {1}.'.format(len(self.copied), self.world.name))

                
    def get_clip_chunkmaps(self):
        """Returns the pixmaps of all the currently selected chunks on this tab."""
        return {(cx, cz): self.scene.itemAt(cx * world.CSIZE, cz * world.CSIZE).pixmap() for cx, cz in self.copied}
    
    
    def paste_chunks(self):
        """Grabs the pixmaps of the selected chunks from the copy tab, adds them to this tab's view,
        and puts this tab into paste mode."""
        if self.win.cliptab is not None:
            self.paste = MBPaste(self.win.cliptab.world.path)
            
            # create pasted selection in this view
            for (cx, cz), chunkmap in self.win.cliptab.get_clip_chunkmaps().iteritems():
                chunk = MBMapChunk(self, (cx, cz))
                chunk.setPixmap(chunkmap)
                chunk.setPos(cx * world.CSIZE, cz * world.CSIZE)
                self.scene.addItem(chunk)
                self.paste.addToGroup(chunk)
                self.paste.chunks[cx, cz] = chunk

            # show paste and darken view
            self.scene.addItem(self.paste)
            self.scene.update()
            
            # move to pasted selection (and update fully to avoid bugs with darkening)
            self.view.setViewportUpdateMode(QtGui.QGraphicsView.FullViewportUpdate)
            self.view.ensureVisible(self.paste)
            self.view.setViewportUpdateMode(QtGui.QGraphicsView.MinimalViewportUpdate)
                
            # clear selection, update gui
            self.selected.clear()
            self.win.update_toolbar()
            self.pastelabel.setText('{0} chunks pasted from {1}.'.format(len(self.paste.chunks), self.win.cliptab.world.name))
            
            
    def merge_chunks(self):
        """Merges a pasted selection of chunks into the current view's chunks,
        and allows further editing of the world."""
        for chunk in self.paste.chunks.itervalues():
            cx, cz = int(chunk.scenePos().x() / world.CSIZE), int(chunk.scenePos().y() / world.CSIZE)
            self.merged[cx, cz] = self.paste.wpath, chunk.coords
            chunk.coords = cx, cz
            
        self.pastelabel.setText('{0} chunks merged.'.format(len(self.paste.chunks)))
        self.scene.destroyItemGroup(self.paste)
        self.paste = None
        self.scene.update()
        self.win.update_toolbar()
        
        
    def cancel_merge(self):
        """Removes a pasted selection without merging it."""
        for chunk in self.paste.chunks.itervalues():
            self.scene.removeItem(chunk)
            
        self.pastelabel.setText('')
        self.scene.destroyItemGroup(self.paste)
        self.paste = None
        self.scene.update()
        self.win.update_toolbar()
        
        
        
class MBPaste(QtGui.QGraphicsItemGroup):
    def __init__(self, wpath):
        QtGui.QGraphicsItemGroup.__init__(self)
        
        self.wpath = wpath
        self.chunks = {}
        
        
    def mousePressEvent(self, event):
        """Records the starting point of a mouse drag on the pasted selection."""
        self.drag_origin = event.scenePos().x(), event.scenePos().y()
        
        
    def mouseMoveEvent(self, event):
        """Moves the pasted selection aroud the view, in chunk-sized increments."""
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
        """Starts a rubber band if the box tool is selected."""
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
        cx, cz = x / world.CSIZE, z / world.CSIZE
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
        
    
        
# startup

if __name__ == '__main__':
    argp = argparse.ArgumentParser('Mine Bash - a Minecraft map editor.')
    argp.add_argument('--world', '-w')
    argp.add_argument('--colours', '-c')
    argp.add_argument('--biomes', '-b')
    args = argp.parse_args()
    
    app = QtGui.QApplication(sys.argv)

    minebash = MineBash(args.world, args.colours, args.biomes)

    sys.exit(app.exec_())


