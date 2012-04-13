import argparse
import os
import sys

from PIL import Image
from PySide import QtGui

from gui import mbwindow
from gui import mbworldtab
from gui import mbmapchunk
from gui import mbpaste
from minebash import orthomap
from minebash import world


class MineBash:
    def __init__(self, wpaths=None, colours=None, biomes=None):
        self.colours = colours
        self.biomes = biomes

        self.win = mbwindow.MBWindow()

        if wpaths:
            for wpath in wpaths.split(','):
                self.add_tab(wpath)
                
        self.win.open.triggered.connect(self.open)
        self.win.save.triggered.connect(self.save)
        self.win.pastebtn.triggered.connect(lambda: self.paste_chunks(self.win.cliptab, self.win.tabs.currentWidget()))


    def save(self):
        """Save merged data to the current world, overwriting it (for now)."""
        tab = self.win.tabs.currentWidget()
        
        # combine merged chunks from all worlds
        newchunks = {}
        for mworld in set(wld for wld, mchunk in tab.merged.itervalues()):
            # get chunks from original world, using original chunk coordinates
            chunks = mworld.get_chunks(set(mchunk.coords for wld, mchunk in tab.merged.itervalues() if wld == mworld))
            # place them in newchunks dict by their new coords
            newchunks.update({(cx, cz): chunks[mchunk.coords] for (cx, cz), (wld, mchunk) in tab.merged.iteritems()})
        
        regionlist = set((cx / world.RSIZE, cz / world.RSIZE) for cx, cz in newchunks.iterkeys())
        for rnum, (rx, rz) in enumerate(regionlist):
            # load existing region, or create a new one
            print 'saving region {0} of {1}:'.format(rnum + 1, len(regionlist), (rx, rz))
            region = tab.world.get_region((rx, rz))
            if not region:
                print 'creating new region'
                region = world.Region(tab.world.path, (rx, rz)) # assumes Anvil for now
            
            # save, using new chunks that are in this region
            region.save({(cx % world.RSIZE, cz % world.RSIZE): chunk for (cx, cz), chunk in newchunks.iteritems()
                         if (cx / world.RSIZE, cz / world.RSIZE) == (rx, rz)})
        
        tab.merged = {}
        self.draw_map(tab, refresh=1, whitelist=newchunks.keys())
    
    
    def open(self):
        """Open a file dialog and return a world path."""
        wpath = QtGui.QFileDialog.getExistingDirectory()
        if os.path.exists(os.path.join(wpath, 'level.dat')):
            self.add_tab(wpath)
            
        else:
            print 'Not a world dir!'
            
            
    def add_tab(self, wpath):
        tab = mbworldtab.MBWorldTab(self.win, world.World(wpath), world.RSIZE, world.CSIZE)

        self.draw_map(tab)

        tab.generate.clicked.connect(lambda: self.draw_map(tab, refresh=1))
        tab.biomecheck.stateChanged.connect(lambda: self.draw_map(tab))

        self.win.tabs.addTab(tab, tab.world.name)
        self.win.tabs.setCurrentWidget(tab)
            
            
    def draw_map(self, tab, refresh=False, whitelist=None):
        """Gets images of all the chunks in the current tab's world,
        as well as any pasted or merged in, and adds their pixmaps to the view.
        Takes an optional chunk whitelist."""
         
        # discard chunk list, as we will be reading fresh from the world file
        if refresh:
            tab.chunks = {}
            
        biomes = tab.biomecheck.isChecked()
            
        # redraw all chunks on the map that need redrawing (regenerating image cache if specified)
        print 'drawing map chunks'
        for (cx, cz), pixmap in self.get_chunk_pixmaps(tab.world, biomes, refresh, whitelist).iteritems():
            if (cx, cz) not in tab.chunks:
                tab.chunks[cx, cz] = mbmapchunk.MBMapChunk(tab, (cx, cz), tab.csize)
                tab.chunks[cx, cz].setPos(cx * tab.csize, cz * tab.csize)
                tab.chunks[cx, cz].setZValue(1)
                tab.scene.addItem(tab.chunks[cx, cz])
            tab.chunks[cx, cz].setPixmap(pixmap)
        
        # redraw pasted selection, if any, from its original world
        if tab.paste:
            print 'redrawing pasted chunks from', tab.paste.world.path
            
            for (cx, cz), pixmap in self.get_chunk_pixmaps(tab.paste.world, biomes, refresh, tab.paste.chunks.keys()).iteritems():
                tab.paste.chunks[cx, cz].setPixmap(pixmap)
                    
        # redraw merged chunks, if any, from each of their original worlds
        if tab.merged:
            print 'redrawing merged chunks'
            
            # merged chunks are indexed by coords in current tab
            # but images must be generated using coords from original world
            for mworld in set(wld for wld, chunk in tab.merged.itervalues()):
                chunklist, mchunks = zip(*((chunk.coords, chunk) for wld, chunk in tab.merged.itervalues() if wld == mworld))
                # draw pixmaps for merged chunks from this world, using their original coords
                pixmaps = self.get_chunk_pixmaps(mworld, biomes, refresh, chunklist)
                for chunk in mchunks:
                    chunk.setPixmap(pixmaps[chunk.coords])
                
        print 'done.'
        print
        
        
    def paste_chunks(self, ctab, ptab):
        """Creates pixmaps of the copied chunks from the copy tab, creates a pasted selection
        and sends it to the paste tab."""
        if ctab is not None:
            paste = mbpaste.MBPaste(ctab.world, ptab.csize)
            
            # create pasted selection in this view
            for (cx, cz), pixmap in self.get_chunk_pixmaps(ctab.world, ptab.biomecheck.isChecked(), whitelist=ctab.copied).iteritems():
                paste.chunks[cx, cz] = mbmapchunk.MBMapChunk(ptab, (cx, cz), world.CSIZE)
                paste.chunks[cx, cz].setPixmap(pixmap)
                paste.chunks[cx, cz].setPos(cx * ptab.csize, cz * world.CSIZE)
                ptab.scene.addItem(paste.chunks[cx, cz])
                paste.addToGroup(paste.chunks[cx, cz])
                    
            ptab.add_paste(paste)
            self.win.update_toolbar()
            
            
    def get_chunk_pixmaps(self, wld, biomes=False, refresh=False, whitelist=None):
        """Gets images of each region and chops them into images of all chunks in the region.
        Returns images as pixmaps. Optionally adds a biome overlay first."""
        pixmaps = {}
        regions = wld.get_region_list(whitelist)
        for rnum, (rx, rz) in enumerate(regions):
            print 'mapping {0} region {1} of {2}'.format(wld.name, rnum + 1, len(regions))
            img = self.get_region_image(wld, (rx, rz), 'block', refresh)
            if biomes:
                img = Image.blend(img, self.get_region_image(wld, (rx, rz), 'biome', refresh), 0.5)
            
            pixmaps.update({(rx * world.RSIZE + cx, rz * world.RSIZE + cz):
                                QtGui.QPixmap.fromImage(QtGui.QImage(
                                    img.crop((cx * world.CSIZE, cz * world.CSIZE, (cx + 1) * world.CSIZE, (cz + 1) * world.CSIZE)).tostring('raw', 'BGRA'),
                                    world.CSIZE, world.CSIZE, QtGui.QImage.Format_ARGB32))
                                for cx, cz in wld.get_region_chunk_list((rx, rz), whitelist)})
        return pixmaps
            
            
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


