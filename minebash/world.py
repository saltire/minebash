import os
import struct
import zlib

import nbt


class World:
    def __init__(self, path):
        self.path = path
        self.rsize = 32
        self.csize = 16
        self.regionlist = self._read_region_list()
        self.regions = {}
        for rx, rz in self.get_region_list():
            self.regions[rx, rz] = Region(self.path, (rx, rz))
        self.chunklist = []
        for region in self.regions.values():
            self.chunklist.extend(region.get_chunk_list())
            
            
    def _get_edges(self, list):
        xrange = [x for (x, z) in list]
        zrange = [z for (x, z) in list]
        return min(xrange), max(xrange), min(zrange), max(zrange)
            
            
    def get_region_edges(self):
        """Returns the highest and lowest values of x and z for all existing regions."""
        return self._get_edges(self.regionlist)
            
            
    def get_chunk_edges(self):
        """Returns the highest and lowest values of x and z for all existing chunks."""
        return self._get_edges(self.chunklist)
            
            
    def get_block_edges(self):
        """Returns the highest and lowest values of x and z for blocks in all existing chunks."""
        cxmin, cxmax, czmin, czmax = self.get_chunk_edges()
        return (
            cxmin * self.csize,
            cxmax * self.csize + self.csize - 1,
            czmin * self.csize,
            czmax * self.csize + self.csize - 1
            )
        
        
    def get_chunk_list(self, list=None):
        """Returns a list of coordinates of all existing chunks (within optional limits)."""
        return [(cx, cz) for (cx, cz) in self.chunklist if list is None or (cx, cz) in list]
            
            
    def get_chunks(self, list=None):
        """Returns a dict of all existing chunks (within optional limits), indexed by coordinates."""
        chunks = {}
        for region in self.regions.values():
            chunks.update(region.read_chunks(list))
        return chunks
    
    
    def get_region_list(self, list=None):
        """Returns a list of coordinates of all existing regions (within optional limits)."""
        return [(rx, rz) for (rx, rz) in self.regionlist if list is None or (rx, rz) in list]
        
        
    def get_regions(self, list=None):
        """Returns a dict of all existing regions (within optional limits), indexed by coordinates."""
        return dict(((rx, rz), self.regions[rx, rz]) for (rx, rz) in self.regions if list is None or (rx, rz) in list)


    def _read_region_list(self):
        """Returns a list of coordinates of all regions in the world directory."""
        regionlist = []
        regionpath = os.path.join(self.path, 'region')
        if os.path.isdir(regionpath):
            for filename in os.listdir(regionpath):
                r, rx, rz, ext = filename.split('.')
                if r == 'r' and ext == 'mcr':
                    regionlist.append((int(rx), int(rz)))
        return regionlist
        


class Region:
    def __init__(self, worldpath, (rx, rz)):
        self.path = os.path.join(worldpath, 'region', 'r.{0}.{1}.mcr'.format(rx, rz))
        self.rsize = 32
        self.csize = 16
        self.coords = (rx, rz)
        self.chunkinfo = self._read_chunk_info()
        
        
    def get_chunk_list(self, list=None):
        """Returns a list of coordinates of existing chunks (within optional limits)."""
        return [(cx, cz) for (cx, cz) in self.chunkinfo.keys() if list is None or (cx, cz) in list]
    
    
    def read_chunks(self, list=None):
        """Returns a list of all existing chunks (within optional limits), indexed by coordinates."""
        with open(self.path, 'rb') as rfile:
            return dict(((cx, cz), self._read_chunk((cx, cz), rfile)) for (cx, cz) in self.chunkinfo.keys() if list is None or (cx, cz) in list)
        
        
    def _read_chunk_info(self):
        """Returns a dict of chunks that exist in the region file, indexed by coords,
        and containing the modification time and sector offset."""
        rx, rz = self.coords
        chunkinfo = {}
        with open(self.path, 'rb') as rfile:
            offsets = struct.unpack_from('>1024i', rfile.read(4096))
            mtimes = struct.unpack_from('>1024i', rfile.read(4096))
            for cz in range(self.rsize):
                for cx in range(self.rsize):
                    index = cx + cz * self.rsize
                    offset = offsets[index]
                    mtime = mtimes[index]
                    ##print '({0}, {1}): Read header {2} at {3}'.format(
                    ##    cx, cz, hex(offset), ((cx + cz * 32) * 4))
                    sectornum = offset / 256 # first sector of chunk (3 bytes)
                    sectorlength = offset % 256 # chunk's length in sectors (1 byte)
                    if sectornum > 0 and sectorlength > 0:
                        chunkinfo[rx * self.rsize + cx, rz * self.rsize + cz] = {'mtime': mtime, 'sectornum': sectornum, 'sectorlength': sectorlength}
        return chunkinfo


    def _read_chunk(self, (cx, cz), rfile):
        rfile.seek(self.chunkinfo[cx, cz]['sectornum'] * 4096)
        length, version = struct.unpack('>ib', rfile.read(5))

        # use ONE of the following two lines:
        data = rfile.read(length - 1) # this trusts that the length field is correct
        #data = rfile.read(self.chunkinfo[(cx, cz)]['sectorlength'] * 4096 - 5).rstrip('\x00') # this does not trust the length field

        if version == 2:
            #print "{0}: Reading data at sector {1} ({2}), stated length {3}, actual length {4}".format(
            #    chunk, hex(chunks[chunk]['sectornum']), chunks[chunk]['sectornum'] * 4096, length, len(data))
            return Chunk(zlib.decompress(data))



class Chunk:
    def __init__(self, data):
        self.csize = 16
        self.cheight = 128
        self.tags = nbt.NBT(data).tags[0][2][0][2]


    def find_tag(self, name):
        """Find the first tag with the given name."""
        return [tag[2] for tag in self.tags if tag[1] == name][0]


    def get_heightmap(self):
        hmapdata = self.find_tag('HeightMap')
        hmap = [] # list of rows, [x][z]
        for z in range(self.csize):
            hmap.append(hmapdata[z * self.csize:(z + 1) * self.csize])
        return zip(*hmap) # the asterisk unpacks the list into arguments for the zip function
    
    
    def get_blocks(self):
        bdata = self.find_tag('Blocks')
        blocks = [] # list of rows, each a vertical list of blocks, [x][z][y]
        for x in range(self.csize):
            row = []
            for z in range(self.csize):
                colstart = x * self.cheight * self.csize + z * self.cheight
                row.append(bdata[colstart:colstart + self.cheight])
            blocks.append(row)
        return blocks


    def get_block_data(self):
        ddata = self.find_tag('Data')
        data = {}
        for y in range(self.cheight):
            for x in range(self.csize):
                for z in range(self.csize):
                    # block data is stored as 4 bits per block, so we have to break each byte in half
                    index = (x * self.cheight * self.csize + z * self.cheight + y)
                    byte = ddata[index]
                    if index % 2:
                        data[x, z, y] = byte % 16 # bottom half
                    else:
                        data[x, z, y] = byte / 16 # top half
        

