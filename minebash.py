import argparse
import os
import sys

from PIL import Image
from PySide import QtGui

from gui import mbwindow
from gui import mbworldtab
from gui import mbmapchunk
from gui import mbpaste
from minebash import world


class MineBash:
    def __init__(self, wpaths=None, colours=None, biomes=None):
        self.win = mbwindow.MBWindow(colours, biomes)

        if wpaths:
            for wpath in wpaths.split(','):
                self.add_tab(wpath)
                
        self.win.open.triggered.connect(self.open)
        self.win.pastebtn.triggered.connect(lambda: self.paste_chunks(self.win.cliptab, self.win.tabs.currentWidget()))


    def open(self):
        """Open a file dialog and return a world path."""
        wpath = QtGui.QFileDialog.getExistingDirectory()
        if os.path.exists(os.path.join(wpath, 'level.dat')):
            self.add_tab(wpath)
            
        else:
            print 'Not a world dir!'
            
            
    def add_tab(self, wpath):
        tab = mbworldtab.MBWorldTab(self.win, world.World(wpath), world.RSIZE, world.CSIZE)

        tab.generate.clicked.connect(lambda: self.draw_map(tab, refresh=1))
        tab.biomecheck.stateChanged.connect(lambda: self.draw_map(tab))
        self.draw_map(tab)

        self.win.tabs.addTab(tab, tab.world.name)
        self.win.tabs.setCurrentWidget(tab)
            
            
    def draw_map(self, tab, refresh=False):
        """Gets images of all the chunks in the current tab's world, as well as any pasted in,
         and adds their pixmaps to the view."""
         
        # discard chunk list, as we will be reading fresh from the world file
        if refresh:
            tab.chunks = {}
        
        # redraw all chunks on the map (regenerating image cache if specified)
        regions = tab.world.get_region_list()
        for rnum, (rx, rz) in enumerate(regions):
            print 'region {0} of {1}:'.format(rnum + 1, len(regions))
            
            for (cx, cz), pixmap in self.get_region_chunk_pixmaps(tab.world, (rx, rz), tab.biomecheck.isChecked(), refresh).iteritems():
                if (cx, cz) not in tab.chunks:
                    tab.chunks[cx, cz] = mbmapchunk.MBMapChunk(tab, (cx, cz), tab.csize)
                    tab.chunks[cx, cz].setPos(cx * tab.csize, cz * tab.csize)
                    tab.scene.addItem(tab.chunks[cx, cz])
                tab.chunks[cx, cz].setPixmap(pixmap)
            
        # redraw pasted selection, if any
        if tab.paste:
            print 'redrawing pasted chunks from', tab.paste.world.path
            
            chunklist = tab.paste.chunks.keys()
            for rx, rz in tab.paste.world.get_region_list(chunklist):
                for (cx, cz), pixmap in self.get_region_chunk_pixmaps(tab.paste.world, (rx, rz), tab.biomecheck.isChecked(), refresh, chunklist).iteritems():
                    tab.paste.chunks[cx, cz].setPixmap(pixmap)
                    
        print 'done.'
        
        
    def paste_chunks(self, ctab, ptab):
        """Creates pixmaps of the copied chunks from the copy tab, creates a pasted selection
        and sends it to the paste tab."""
        if ctab is not None:
            paste = mbpaste.MBPaste(ctab.world, ptab.csize)
            
            # create pasted selection in this view
            chunklist = ctab.copied
            for rx, rz in ctab.world.get_region_list(chunklist):
                for (cx, cz), pixmap in self.get_region_chunk_pixmaps(ctab.world, (rx, rz), ptab.biomecheck.isChecked(), whitelist=chunklist).iteritems():
                    chunk = mbmapchunk.MBMapChunk(ptab, (cx, cz), world.CSIZE)
                    chunk.setPixmap(pixmap)
                    chunk.setPos(cx * ptab.csize, cz * world.CSIZE)
                    ptab.scene.addItem(chunk)
                    paste.addToGroup(chunk)
                    paste.chunks[cx, cz] = chunk
                    
            ptab.add_paste(paste)
            self.win.update_toolbar()
            
            
    def get_region_chunk_pixmaps(self, wld, (rx, rz), biomes=False, refresh=False, whitelist=None):
        """Gets an image of a region and chops it into images of all chunks in the region.
        Returns images as pixmaps. Optionally adds a biome overlay first."""
        img = self.get_region_image(wld, (rx, rz), 'block', refresh)
        if biomes:
            img = Image.blend(img, self.get_region_image(wld, (rx, rz), 'biome', refresh), 0.5)
            
        return {(rx * world.RSIZE + cx, rz * world.RSIZE + cz):
                    QtGui.QPixmap.fromImage(QtGui.QImage(
                        img.crop((cx * world.CSIZE, cz * world.CSIZE, (cx + 1) * world.CSIZE, (cz + 1) * world.CSIZE)).tostring('raw', 'BGRA'),
                        world.CSIZE, world.CSIZE, QtGui.QImage.Format_ARGB32))
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
            img = orthomap.OrthoMap(wld, self.colours, self.biomes).draw_region((rx, rz), type)
            img.save(path)
            print 'cached', path

        return img
    

        
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


