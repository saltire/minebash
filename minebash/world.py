import os
import struct
import zlib

import numpy

import nbt


RSIZE = 32
CSIZE = 16
SECTIONS = 16
SECHEIGHT = 16
CHEIGHT = 128


def crop_coords(self, coords, bcrop=None, scale=1):
    """Filter a list of coordinates by a bounding box.
    Coordinates are at block scope, divided by scale if specified."""
    if bcrop is None:
        return coords
    w, e, n, s = (i / scale for i in bcrop)
    return [(x, z) for (x, z) in coords if w <= x <= e and n <= z <= s]



class World:
    def __init__(self, path, force_region=0):
        self.path = path
        self.name = os.path.basename(path)
        self.anvil = 0
        self.regionlist = self._read_region_list(force_region)

        self.regions = {}
        self.chunklist = set()
        for rx, rz in self.get_region_list():
            self.regions[rx, rz] = (AnvilRegion if self.anvil else Region)(self.path, (rx, rz))
            for cx, cz in self.regions[rx, rz].get_chunk_list():
                self.chunklist.add((rx * RSIZE + cx, rz * RSIZE + cz))
            
            
    def get_chunk_list(self, whitelist=None):
        """Returns a list of coordinates of all existing chunks (within optional whitelist)."""
        if whitelist is None:
            return self.chunklist
        else:
            return [(cx, cz) for (cx, cz) in self.chunklist if (cx, cz) in whitelist]
    
    
    def get_chunks(self, whitelist=None):
        """Returns a dict of all existing chunks (within optional chunk whitelist), indexed by coordinates."""
        chunks = {}
        for region in self.regions.values():
            chunks.update(region.read_chunks(whitelist))
        return chunks
    
    
    def get_chunk(self, (cx, cz)):
        """Get a single chunk, from the appropriate region."""
        return self.regions[rx, rz].read_chunks([(cx, cz)])
    
    
    def get_region_list(self, whitelist=None):
        """Returns a list of coordinates of all existing regions (within optional chunk whitelist)."""
        if whitelist is None:
            return self.regionlist
        else:
            region_whitelist = ((cx / RSIZE, cz / RSIZE) for (cx, cz) in whitelist)
            return [(rx, rz) for (rx, rz) in self.regionlist if (rx, rz) in region_whitelist]
        
        
    def get_regions(self, whitelist=None):
        """Returns a dict of all existing regions (within optional chunk whitelist), indexed by coordinates."""
        return {(rx, rz): self.regions[rx, rz] for (rx, rz) in self.get_region_list(whitelist)}
    
    
    def get_region(self, (rx, rz)):
        """Returns a region at a specific coordinate, if it exists."""
        return self.regions[rx, rz] if (rx, rz) in self.regions else None


    def _read_region_list(self, force_region=0):
        """Returns a list of coordinates of all regions in the world directory.
        Setting force_region to true forces it to look for the old region format."""
        anvillist = []
        regionlist = []
        regionpath = os.path.join(self.path, 'region')
        if not os.path.isdir(regionpath):
            print "Dir doesn't exist!"
            
        else:
            for filename in os.listdir(regionpath):
                r, rx, rz, ext = filename.split('.')
                if r == 'r' and ext == 'mca':
                    anvillist.append((int(rx), int(rz)))
                elif r == 'r' and ext == 'mcr':
                    regionlist.append((int(rx), int(rz)))
                    
        self.anvil = 1 if anvillist and not force_region else 0 
        return anvillist if anvillist and not force_region else regionlist
    
    
    
class Region:
    def __init__(self, worldpath, (rx, rz), anvil=0):
        self.path = os.path.join(worldpath, 'region', 'r.{0}.{1}.mcr'.format(rx, rz))
        self.coords = rx, rz
        self.chunkinfo = self._read_chunk_info()
        
        
    def get_chunk_list(self, whitelist=None):
        """Returns a list of LOCAL chunk coordinates existing in the region file,
        within an optional whitelist of GLOBAL chunk coordinates."""
        if whitelist is None:
            return self.chunkinfo.keys()
        else:
            rx, rz = self.coords
            return [(cx, cz) for (cx, cz) in self.chunkinfo.keys()
                    if (rx * RSIZE + cx, rz * RSIZE + cz) in whitelist]
    
    
    def read_chunks(self, whitelist=None):
        """Returns a dict of all chunks in the region (within an optional chunk whitelist),
        indexed by local chunk coordinates."""
        chunklist = self.get_chunk_list(whitelist)
        if not chunklist:
            return []
        
        with open(self.path, 'rb') as rfile:
            return {(cx, cz): self._read_chunk((cx, cz), rfile) for (cx, cz) in chunklist}
        
        
    def _read_chunk_info(self):
        """Returns a dict of chunks that exist in the region file, indexed by coords,
        and containing the modification time and sector offset."""
        rx, rz = self.coords
        chunkinfo = {}
        with open(self.path, 'rb') as rfile:
            offsets = struct.unpack_from('>1024i', rfile.read(4096))
            mtimes = struct.unpack_from('>1024i', rfile.read(4096))
            for cz in range(RSIZE):
                for cx in range(RSIZE):
                    index = cx + cz * RSIZE
                    offset = offsets[index]
                    mtime = mtimes[index]
                    #print '({0}, {1}): Read header {2} at {3}'.format(
                    #    cx, cz, hex(offset), ((cx + cz * 32) * 4))
                    sectornum = offset / 256 # first sector of chunk (3 bytes)
                    sectorlength = offset % 256 # chunk's length in sectors (1 byte)
                    if sectornum > 0 and sectorlength > 0:
                        chunkinfo[cx, cz] = {'mtime': mtime, 'sectornum': sectornum, 'sectorlength': sectorlength}
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
        self.coords = rx, rz
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
        self.cheight = 128
        self.tags = nbt.NBT(data).tags[0][2][0][2]


    def find_tag(self, name, container=None):
        """Find the first tag with the given name."""
        container = container if container is not None else self.tags
        return [tag[2] for tag in container if tag[1] == name][0]
    
    
    def get_heightmap(self):
        hmapdata = self.find_tag('HeightMap')
        hmap = numpy.zeros((CSIZE, CSIZE), numpy.ubyte) # x, z
        for z in range(CSIZE):
            hmap[:, z] = hmapdata[z * CSIZE:(z + 1) * CSIZE]
        return hmap
    
    
    def get_blocks(self):
        bdata = self.find_tag('Blocks')
        blocks = numpy.zeros((CSIZE, CSIZE, self.cheight), numpy.uint16) # x, z, y
        for x in range(CSIZE):
            for z in range(CSIZE):
                colstart = x * self.cheight * CSIZE + z * self.cheight
                blocks[x, z, :] = bdata[colstart:colstart + self.cheight]
        return blocks


    def get_block_data(self):
        ddata = self.find_tag('Data')
        data = []
        for x in range(CSIZE):
            data.append([])
            for z in range(CSIZE):
                data[x].append([])
                for y in range(self.cheight):
                    byte = ddata[x * self.cheight * CSIZE + z * self.cheight + y]
                    # block data is stored as 4 bits per block, so we have to break each byte in half
                    data[x][z].append(byte % 16 if y % 2 else byte / 16)
        return data

        

class AnvilChunk(Chunk):
    def __init__(self, data):
        self.tags = nbt.NBT(data).tags[0][2][0][2]
        
        
    def get_blocks(self):
        blocks = numpy.zeros((CSIZE, CSIZE, SECHEIGHT * SECTIONS), numpy.uint16) # x, z, y
        sections = {}
        for section in [tag[2] for tag in self.find_tag('Sections')[1]]:
            sections[self.find_tag('Y', section)] = self.find_tag('Blocks', section)
        
        for x in range(CSIZE):
            for z in range(CSIZE):
                for s, section in sections.items():
                    sya = s * SECHEIGHT
                    syb = sya + SECHEIGHT
                    start = CSIZE * z + x
                    # get a Y column from data stored in YZX order
                    blocks[x, z, sya:syb] = section[start:start + SECHEIGHT * CSIZE * CSIZE:CSIZE * CSIZE]
        
        # also have to implement the extra data layer in the anvil format
        
        return blocks
    
    
    def get_biomes(self):
        bidata = self.find_tag('Biomes')
        biomes = numpy.zeros((CSIZE, CSIZE), numpy.ubyte) # x, z
        for z in range(CSIZE):
            biomes[:, z] = bidata[z * CSIZE:(z + 1) * CSIZE]
        return biomes

