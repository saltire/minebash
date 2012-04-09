from PySide import QtGui

import mbmapchunk
import mbmapview
import mbpaste


class MBWorldTab(QtGui.QWidget):
    def __init__(self, win, wld, rsize, csize):
        QtGui.QWidget.__init__(self)
        
        self.win = win
        self.world = wld
        self.rsize = rsize
        self.csize = csize
        
        self.chunks = {} # dict of chunks indexed by coords
        self.selected = set() # currently selected chunks in this world
        self.copied = set() # last copied chunks in this world
        self.select = True # whether tools will select or deselect chunks
        self.paste = None # a pasted, unmerged selection of chunks
        self.merged = {} # dict of merged chunk info
        
        self.init_ui()

        
    def init_ui(self):
        mainlayout = QtGui.QVBoxLayout(self)
        mainlayout.setContentsMargins(10, 10, 10, 10)
        mainlayout.setSpacing(0)

        self.scene = QtGui.QGraphicsScene(self)
        self.scene.setBackgroundBrush(QtGui.QColor(25, 25, 25))
        
        self.view = mbmapview.MBMapView(self.scene, self)
        
        tools = QtGui.QFrame(self)
        info = QtGui.QFrame(self)
        mainlayout.addWidget(self.view)
        mainlayout.addWidget(info)
        mainlayout.addWidget(tools)
        
        # tools row
        
        toolslayout = QtGui.QHBoxLayout(tools)
        toolslayout.setSpacing(10)
        toolslayout.setSizeConstraint(QtGui.QLayout.SetMinimumSize)
        
        self.pastelabel = QtGui.QLabel('')
        toolslayout.addWidget(self.pastelabel)
        
        toolslayout.addStretch()
        
        self.generate = QtGui.QPushButton('Generate', self)
        toolslayout.addWidget(self.generate)
        
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
        infolayout.addWidget(self.biomecheck)

        
    def clear_labels(self):
        """Clears the coordinate labels."""
        for text, label in self.labels.items():
            label.setText('{0}:'.format(text))
        
        
    def update_labels(self, x, z):
        """Updates coordinate labels with the region, chunk, and block under the mouse cursor."""
        cx, cz = x / self.csize, z / self.csize
        rx, rz = cx / self.csize, cz / self.csize
        self.labels['Block'].setText('Block: {0}, {1}'.format(x, z))
        self.labels['Chunk'].setText('Chunk: {0}, {1}'.format(cx, cz))
        self.labels['Region'].setText('Region: {0}, {1}'.format(rx, rz))
            
            
    def highlight_chunk(self, (cx, cz)):
        """Mark a chunk to be highlighted by a selection tool."""
        if (cx, cz) in self.chunks:
            self.scene.itemAt(cx * self.csize, cz * self.csize).setSelected(1)

        
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
        return {(cx, cz): self.scene.itemAt(cx * self.csize, cz * self.csize).pixmap() for cx, cz in self.copied}
    
    
    def paste_chunks(self):
        """Grabs the pixmaps of the selected chunks from the copy tab, adds them to this tab's view,
        and puts this tab into paste mode."""
        if self.win.cliptab is not None:
            self.paste = mbpaste.MBPaste(self.world, self.csize)
            
            # create pasted selection in this view
            for (cx, cz), chunkmap in self.win.cliptab.get_clip_chunkmaps().iteritems():
                chunk = mbmapchunk.MBMapChunk(self, (cx, cz), self.csize)
                chunk.setPixmap(chunkmap)
                chunk.setPos(cx * self.csize, cz * self.csize)
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
            cx, cz = int(chunk.scenePos().x() / self.csize), int(chunk.scenePos().y() / self.csize)
            self.merged[cx, cz] = self.paste.world.path, chunk.coords
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
        
        
        