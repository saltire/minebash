import argparse
import os
import sys

from PIL import Image
from PySide import QtGui

from gui import mbwindow
from gui import mbworldtab
from gui import mbmapchunk
from gui import mbpaste
from minebash import nbt
from minebash import orthomap
from minebash import world


class MineBash:
    def __init__(self, wpaths=None, colourpath=None, biomepath=None):
        self.colourpath = colourpath if colourpath else 'colours.csv'
        self.biomepath = biomepath if biomepath else 'biomes.csv'
        
        # biome names
        self.biomes = {}
        with open(self.biomepath, 'rb') as cfile:
            for line in cfile.readlines():
                if line.strip() and line[0] != '#':
                    values = line.split(',')
                    self.biomes[int(values[0])] = values[4]

        self.win = mbwindow.MBWindow()

        if wpaths:
            for wpath in wpaths.split(','):
                self._add_tab(wpath)
                
        self.win.open.triggered.connect(self.open)
        self.win.save.triggered.connect(self.save)
        self.win.pastebtn.triggered.connect(lambda: self.paste_chunks(self.win.cliptab, self.win.tabs.currentWidget()))


    def save(self):
        """Save merged data to the current world, overwriting it (for now)."""
        tab = self.win.tabs.currentWidget()
        
        newchunks = {}
        for wld, wchunks in tab.merged.iteritems():
            # get chunks from original world, using original chunk coordinates
            chunks = wld.get_chunks([wchunk.coords for wchunk in wchunks.itervalues()])
            # place them in newchunks dict by their new coords
            newchunks.update({(cx, cz): chunks[wchunk.coords] for (cx, cz), wchunk in wchunks.iteritems()})
            
        regionlist = set((cx / world.RSIZE, cz / world.RSIZE) for cx, cz in wchunks.iterkeys())
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
        self.draw_map(tab, refresh=1, regionlist=regionlist)
    
    
    def open(self):
        """Open a file dialog and return a world path."""
        wpath = QtGui.QFileDialog.getExistingDirectory()
        if os.path.exists(os.path.join(wpath, 'level.dat')):
            self._add_tab(wpath)
            
        else:
            print 'Not a world dir!'
            
            
    def _add_tab(self, wpath):
        tab = mbworldtab.MBWorldTab(self.win, world.World(wpath), world.RSIZE, world.CSIZE, self.biomes)

        self.draw_map(tab)

        tab.generate.clicked.connect(lambda: self.draw_map(tab, refresh=1))
        tab.biomecheck.stateChanged.connect(lambda: self.draw_map(tab))

        self.win.tabs.addTab(tab, tab.world.name)
        self.win.tabs.setCurrentWidget(tab)
            
            
    def draw_map(self, tab, refresh=False, regionlist=None):
        """Gets images of all the chunks in the current tab's world, as well as any pasted in,
         and adds their pixmaps to the view. Also refresh metadata."""
         
        # discard chunk list, as we will be reading fresh from the world file
        if refresh:
            tab.chunks = {}
            
        # whether to draw biome overlay
        biomes = tab.biomecheck.isChecked() and tab.world.anvil
        
        # redraw all chunks on the map (regenerating image cache if specified)
        regions = set((rx, rz) for (rx, rz) in tab.world.get_region_list() if regionlist is None or (rx, rz) in regionlist)
        for rnum, (rx, rz) in enumerate(regions):
            print 'mapping {0} region {1} of {2}:'.format(tab.world.name, rnum + 1, len(regions))
            
            print 'biome data'
            if biomes:
                bdata = self._get_region_biome_data(tab.world, (rx, rz), refresh)
            print 'pixmaps'
            pixmaps = self._get_region_chunk_pixmaps(tab.world, (rx, rz), biomes, refresh)
            for cx, cz in ((rx * world.RSIZE + cx, rz * world.RSIZE + cz)
                          for cz in range(world.RSIZE) for cx in range(world.RSIZE)
                              if (cx, cz) in tab.world.get_region_chunk_list((rx, rz))):
                # create chunk if necessary, and set pixmap
                if (cx, cz) not in tab.chunks:
                    tab.chunks[cx, cz] = mbmapchunk.MBMapChunk(tab, (cx, cz), tab.csize)
                    tab.chunks[cx, cz].setPos(cx * tab.csize, cz * tab.csize)
                    tab.scene.addItem(tab.chunks[cx, cz])
                tab.chunks[cx, cz].setPixmap(pixmaps[cx, cz])
                
                # set metadata
                if biomes:
                    tab.biomedata[cx, cz] = bdata[cx % world.RSIZE, cz % world.RSIZE]
            
        # redraw pasted selection, if any, from its original world
        if tab.paste:
            print 'redrawing pasted chunks from', tab.paste.world.path
            
            chunklist = tab.paste.chunks.keys()
            for rx, rz in tab.paste.world.get_region_list(chunklist):
                for (cx, cz), pixmap in self._get_region_chunk_pixmaps(tab.paste.world, (rx, rz), biomes, refresh, chunklist).iteritems():
                    tab.paste.chunks[cx, cz].setPixmap(pixmap)
                    
        # redraw merged chunks, if any, from each of their original worlds
        if tab.merged:
            print 'redrawing merged chunks'
            
            # merged chunks are indexed by coords in current tab
            # but images must be generated using coords from original world
            for wld, wchunks in tab.merged.iteritems():
                # get original coords of all merged chunks from this world
                chunklist = [wchunk.coords for wchunk in wchunks.itervalues()]
                # draw pixmaps for merged chunks from this world, a region at a time
                pixmaps = {}
                for rx, rz in wld.get_region_list(chunklist):
                    pixmaps.update(self._get_region_chunk_pixmaps(wld, (rx, rz), tab.biomecheck.isChecked(), refresh, chunklist))
                # update merged chunks with pixmaps from their original coords
                for wchunk in wchunks.itervalues():
                    wchunk.setPixmap(pixmaps[wchunk.coords])
                
        print 'done.'
        print
        
        
    def paste_chunks(self, ctab, ptab):
        """Creates pixmaps of the copied chunks from the copy tab, creates a pasted selection
        and sends it to the paste tab."""
        if ctab is not None:
            paste = mbpaste.MBPaste(ctab.world, ptab.csize)
            
            # create pasted selection in this view
            chunklist = ctab.copied
            for rx, rz in ctab.world.get_region_list(chunklist):
                for (cx, cz), pixmap in self._get_region_chunk_pixmaps(ctab.world, (rx, rz), ptab.biomecheck.isChecked(), whitelist=chunklist).iteritems():
                    chunk = mbmapchunk.MBMapChunk(ptab, (cx, cz), world.CSIZE)
                    chunk.setPixmap(pixmap)
                    chunk.setPos(cx * ptab.csize, cz * world.CSIZE)
                    ptab.scene.addItem(chunk)
                    paste.addToGroup(chunk)
                    paste.chunks[cx, cz] = chunk
                    
            ptab.add_paste(paste)
            self.win.update_toolbar()
            
            
    def _get_region_biome_data(self, wld, (rx, rz), refresh=False):
        #cachepath = os.path.join(os.getcwd(), 'cache', wld.name)
        #if not os.path.exists(cachepath):
        #    os.makedirs(cachepath)
        #path = os.path.join(cachepath, 'bdata_{0}.{1}.txt'.format(rx, rz))
        #if os.path.exists(path) and not refresh:
        #    # use cached metadata
        #    print 'found', path
        #    bdata = nbt.NBTReader().from_file(path)[0][2]
        #else:
        #    # read biome data and cache it
        #    for (cx, cz), chunk in sorted(tab.world.get_region_chunks((rx, rz)).iteritems()):
        #        bdata = chunk.get_data('biome')
        #        tag = ('Byte Array', 'Chunk Biomes', [])
        #        ...
        return {(cx, cz): chunk.get_data('biome') for (cx, cz), chunk in wld.get_region_chunks((rx, rz)).iteritems()}
            
            
    def _get_region_chunk_pixmaps(self, wld, (rx, rz), biomes=False, refresh=False, whitelist=None):
        """Gets an image of a region and chops it into images of all chunks in the region.
        Returns images as pixmaps. Optionally adds a biome overlay first."""
        img = self._get_region_image(wld, (rx, rz), 'block', refresh)
        if biomes:
            img = Image.blend(img, self._get_region_image(wld, (rx, rz), 'biome', refresh), 0.5)
            
        return {(rx * world.RSIZE + cx, rz * world.RSIZE + cz):
                    QtGui.QPixmap.fromImage(QtGui.QImage(
                        img.crop((cx * world.CSIZE, cz * world.CSIZE, (cx + 1) * world.CSIZE, (cz + 1) * world.CSIZE)).tostring('raw', 'BGRA'),
                        world.CSIZE, world.CSIZE, QtGui.QImage.Format_ARGB32))
                    for cx, cz in wld.get_region_chunk_list((rx, rz), whitelist)}
    
    
    def _get_region_image(self, wld, (rx, rz), type='block', refresh=False, whitelist=None):
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
            img = orthomap.OrthoMap(wld, self.colourpath, self.biomepath).draw_region((rx, rz), type)
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


