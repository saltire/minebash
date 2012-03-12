import os
import struct
import zlib

import numpy

import nbt


class World:
    def __init__(self, path, force_region=0):
        self.rsize = 32
        self.csize = 16
        
        self.path = path
        self.anvil = 0
        self.regionlist = self._read_region_list(force_region)

        self.regions = {}
        for rx, rz in self.get_region_list():
            self.regions[rx, rz] = (AnvilRegion if self.anvil else Region)(self.path, (rx, rz))
        self.chunklist = []
        for region in self.regions.values():
            self.chunklist.extend(region.get_chunk_list())
            
            
    def get_chunk_list(self, limits=None):
        """Returns a list of coordinates of all existing chunks (within optional chunk limits)."""
        return self._get_coords_in_limits(self.chunklist, limits, self.csize)
            
            
    def get_chunks(self, limits=None):
        """Returns a dict of all existing chunks (within optional chunk limits), indexed by coordinates."""
        chunks = {}
        for region in self.get_regions(limits, self.rsize).values():
            chunklist = self._get_coords_in_limits(region.get_chunk_list(), self.csize)
            chunks.update(region.read_chunks(chunklist))
        return chunks
    
    
    def get_region_list(self, limits=None):
        """Returns a list of coordinates of all existing regions (within optional chunk limits)."""
        return self._get_coords_in_limits(self.regionlist, limits, self.rsize * self.csize)
        
        
    def get_regions(self, limits=None):
        """Returns a dict of all existing regions (within optional chunk limits), indexed by coordinates."""
        return dict(((rx, rz), self.regions[rx, rz]) for (rx, rz) in self.get_region_list(limits))


    def _read_region_list(self, force_region=0):
        """Returns a list of coordinates of all regions in the world directory."""
        anvillist = []
        regionlist = []
        regionpath = os.path.join(self.path, 'region')
        if os.path.isdir(regionpath):
            for filename in os.listdir(regionpath):
                r, rx, rz, ext = filename.split('.')
                if r == 'r' and ext == 'mca':
                    anvillist.append((int(rx), int(rz)))
                elif r == 'r' and ext == 'mcr':
                    regionlist.append((int(rx), int(rz)))
                    
        self.anvil = 1 if anvillist and not force_region else 0 
        return anvillist if anvillist and not force_region else regionlist
    
    
    def _get_coords_in_limits(self, coords, limits=None, scale=1):
        """Filter a list of coordinates by a bounding box.
        Coordinates are at chunk scope, divided by scale if specified."""
        if limits is None:
            return coords
        w, e, n, s = [i / scale for i in limits]
        return [(x, z) for (x, z) in coords if w <= x <= e and n <= z <= s]
    
    
    
class Region:
    def __init__(self, worldpath, (rx, rz), anvil=0):
        self.path = os.path.join(worldpath, 'region', 'r.{0}.{1}.mcr'.format(rx, rz))
        self.rsize = 32
        self.csize = 16
        self.coords = (rx, rz)
        self.chunkinfo = self._read_chunk_info()
        
        
    def get_chunk_list(self, list=None):
        """Returns a list of coordinates of chunks existing in the region file."""
        return self.chunkinfo.keys()
    
    
    def read_chunks(self, whitelist=None):
        """Returns a dict of all existing chunks (within an optional whitelist), indexed by coordinates."""
        with open(self.path, 'rb') as rfile:
            return dict(((cx, cz), self._read_chunk((cx, cz), rfile)) for (cx, cz) in self.chunkinfo.iterkeys() if whitelist is None or (cx, cz) in whitelist)
        
        
    # experimental function to see if it would improve speed, but didn't really
    def read_all_chunks(self, whitelist=None):
        """Returns a dict of all existing chunks (within an optional whitelist), indexed by coordinates.
        This method loads all chunks in a single read, rather than seeking to each one individually."""
        with open(self.path, 'rb') as rfile:
            rfile.seek(8192)
            cdata = rfile.read()
        
        chunks = {}
        for (cx, cz), cinfo in self.chunkinfo.iteritems():
            cstart = (cinfo['sectornum'] - 2) * 4096
            cend = (cinfo['sectornum'] - 2 + cinfo['sectorlength']) * 4096
            chunk = cdata[cstart:cend]
            length, version = struct.unpack('>ib', chunk[:5])
            if version == 2:
                chunks[cx, cz] = Chunk(zlib.decompress(chunk[5:length + 4]))
                
        return dict(((cx, cz), chunks[cx, cz]) for (cx, cz) in chunks.iterkeys() if whitelist is None or (cx, cz) in whitelist)
    
    
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
                    #print '({0}, {1}): Read header {2} at {3}'.format(
                    #    cx, cz, hex(offset), ((cx + cz * 32) * 4))
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



class AnvilRegion(Region):
    def __init__(self, worldpath, (rx, rz)):
        self.path = os.path.join(worldpath, 'region', 'r.{0}.{1}.mca'.format(rx, rz))
        self.rsize = 32
        self.csize = 16
        self.coords = (rx, rz)
        self.chunkinfo = self._read_chunk_info()


    def _read_chunk(self, (cx, cz), rfile):
        rfile.seek(self.chunkinfo[cx, cz]['sectornum'] * 4096)
        length, version = struct.unpack('>ib', rfile.read(5))

        # use ONE of the following two lines:
        data = rfile.read(length - 1) # this trusts that the length field is correct
        #data = rfile.read(self.chunkinfo[(cx, cz)]['sectorlength'] * 4096 - 5).rstrip('\x00') # this does not trust the length field

        if version == 2:
            #print "{0}: Reading data at sector {1} ({2}), stated length {3}, actual length {4}".format(
            #    (cx, cz), hex(self.chunkinfo[cx, cz]['sectornum']), hex(self.chunkinfo[cx, cz]['sectornum'] * 4096), length, len(data))
            return AnvilChunk(zlib.decompress(data))

    
    
class Chunk:
    def __init__(self, data):
        self.csize = 16
        self.cheight = 128
        self.tags = nbt.NBT(data).tags[0][2][0][2]


    def find_tag(self, name, container=None):
        """Find the first tag with the given name."""
        container = container if container is not None else self.tags
        return [tag[2] for tag in container if tag[1] == name][0]
    
    
    def get_heightmap(self):
        hmapdata = self.find_tag('HeightMap')
        hmap = [] # list of rows, columns,[x][z]
        for z in range(self.csize):
            hmap.append(hmapdata[z * self.csize:(z + 1) * self.csize])
        return zip(*hmap) # the asterisk unpacks the list into arguments for the zip function
    
    
    def get_blocks(self):
        bdata = self.find_tag('Blocks')
        blocks = [] # list of rows, columns, blocks, [x][z][y]
        for x in range(self.csize):
            blocks.append([])
            for z in range(self.csize):
                colstart = x * self.cheight * self.csize + z * self.cheight
                blocks[x].append(bdata[colstart:colstart + self.cheight])
        return blocks


    def get_block_data(self):
        ddata = self.find_tag('Data')
        data = []
        for x in range(self.csize):
            data.append([])
            for z in range(self.csize):
                data[x].append([])
                for y in range(self.cheight):
                    byte = ddata[x * self.cheight * self.csize + z * self.cheight + y]
                    # block data is stored as 4 bits per block, so we have to break each byte in half
                    data[x][z].append(byte % 16 if y % 2 else byte / 16)
        return data

        

class AnvilChunk(Chunk):
    def __init__(self, data):
        self.csize = 16
        self.sections = 16
        self.secheight = 16
        self.tags = nbt.NBT(data).tags[0][2][0][2]
        
        
    def get_blocks(self):
        blocks = numpy.zeros((16, 16, 256), numpy.int16) # x, z, y
        sections = {}
        for section in [tag[2] for tag in self.find_tag('Sections')[1]]:
            sections[self.find_tag('Y', section)] = self.find_tag('Blocks', section)
        
        for x in range(self.csize):
            for z in range(self.csize):
                for s, section in sections.items():
                    sya = s * self.secheight
                    syb = sya + self.secheight
                    start = self.csize * z + x
                    # get a Y column from data stored in YZX order
                    blocks[x, z, sya:syb] = section[start:start + self.secheight * self.csize * self.csize:self.csize * self.csize]
        
        return blocks

    
    def get_blocks_old(self):
        blocks = [] # list of rows, columns, blocks, [x][z][y]
        sections = {}
        for section in [tag[2] for tag in self.find_tag('Sections')[1]]:
            sections[self.find_tag('Y', section)] = self.find_tag('Blocks', section)
        
        for x in range(self.csize):
            blocks.append([])
            for z in range(self.csize):
                blocks[x].append([])
                for s in range(self.sections):
                    if s not in sections:
                        blocks[x][z].extend([0] * self.secheight)
                    else:
                        for sy in range(self.secheight):
                            blocks[x][z].append(sections[s][sy * self.csize * self.csize + z * self.csize + x])
        
        return blocks

