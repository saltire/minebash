import math
import os
import struct
import time
import zlib

import numpy

import nbt


RSIZE = 32
CSIZE = 16
SECTIONS = 16
SECHEIGHT = 16
CHEIGHT = 128


class World:
    def __init__(self, path, force_region=0):
        self.path = path
        self.name = os.path.basename(path)
        self.anvil = 0
        self.regionlist = self._read_region_list(force_region)

        self.regions = {}
        for rx, rz in self.get_region_list():
            self.regions[rx, rz] = (AnvilRegion if self.anvil else Region)(self.path, (rx, rz))
            
            
    def get_chunk_list(self, whitelist=None):
        """Returns a list of global coordinates of all existing chunks,
        within an optional whitelist of global chunk coordinates."""
        return [(rx * RSIZE + cx, rz * RSIZE + cz)
                for (rx, rz), region in self.regions.iteritems()
                    for cx, cz in region.get_chunk_list(whitelist)]
    
    
    def get_chunks(self, whitelist=None):
        """Returns a dict of all existing chunks, indexed by global chunk coordinates,
        within an optional whitelist of global chunk coordinates."""
        return {(rx * RSIZE + cx, rz * RSIZE + cz): chunk
                for (rx, rz), region in self.regions.iteritems()
                    for (cx, cz), chunk in region.read_chunks(whitelist).iteritems()}
    
    
    def get_chunk(self, (cx, cz)):
        """Get a single chunk, from the appropriate region."""
        return self.regions[rx, rz].read_chunks([(cx, cz)])
    
    
    def get_region_chunk_list(self, (rx, rz), whitelist=None):
        """Returns a list of REGIONAL chunk coordinates existing in the given region file,
        within an optional whitelist of GLOBAL chunk coordinates."""
        return self.regions[rx, rz].get_chunk_list(whitelist)
    
    
    def get_region_chunks(self, (rx, rz), whitelist=None):
        """Returns a dict of chunks in this region, indexed by REGIONAL chunk coordinates,
        within an optional whitelist of GLOBAL chunk coordinates."""
        return self.regions[rx, rz].read_chunks(whitelist)


    def get_region_list(self, whitelist=None):
        """Returns a list of coordinates of all existing regions,
         within an optional whitelist of global chunk coordinates."""
        if whitelist is None:
            return self.regionlist
        else:
            region_whitelist = set((cx / RSIZE, cz / RSIZE) for (cx, cz) in whitelist)
            return [(rx, rz) for rx, rz in self.regionlist if (rx, rz) in region_whitelist]
        
        
    def get_regions(self, whitelist=None):
        """Returns a dict of all existing regions, indexed by region coordinates,
        within an optional whitelist of global chunk coordinates."""
        return {(rx, rz): self.regions[rx, rz] for rx, rz in self.get_region_list(whitelist)}
    
    
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
        print 'World type is {0}'.format('Anvil' if self.anvil else 'McRegion')
        return anvillist if anvillist and not force_region else regionlist
    
    
    
class Region:
    def __init__(self, worldpath, (rx, rz)):
        self.path = os.path.join(worldpath, 'region', 'r.{0}.{1}.mcr'.format(rx, rz))
        self.coords = rx, rz
        self.chunkinfo = self._read_chunk_info()
        
        
    def get_chunk_list(self, whitelist=None):
        """Returns a list of REGIONAL chunk coordinates existing in the region file,
        within an optional whitelist of GLOBAL chunk coordinates."""
        if whitelist is None:
            return self.chunkinfo.keys()
        else:
            rx, rz = self.coords
            return [(cx, cz) for cx, cz in self.chunkinfo.keys()
                    if (rx * RSIZE + cx, rz * RSIZE + cz) in whitelist]
    
    
    def read_chunks(self, whitelist=None):
        """Returns a dict of all chunks in the region, indexed by REGIONAL chunk coordinates,
        within an optional whitelist of GLOBAL chunk coordinates."""
        chunklist = self.get_chunk_list(whitelist)
        if not chunklist or not os.path.exists(self.path):
            return {}
        
        print self.chunkinfo
        
        print 'reading', self.path
        with open(self.path, 'rb') as rfile:
            return {(cx, cz): self._read_chunk((cx, cz), rfile) for cx, cz in chunklist}
        
        
    def save(self, newchunks={}):
        print 'doing save'
        print newchunks
        oldchunks = self.read_chunks()

        if not os.path.exists(os.path.dirname(self.path)):
            os.makedirs(os.path.dirname(self.path))
            
        print len(oldchunks), 'old chunks'
        print len(newchunks), 'new chunks'
        print len([cx for cx, cz in oldchunks if (cx, cz) in newchunks]), 'chunks to replace'
        
        with open(self.path, 'wb') as rfile:
            sectornum = 2
            version = 2
            for cz in range(RSIZE):
                for cx in range(RSIZE):
                    if (cx, cz) in newchunks:
                        data = newchunks[cx, cz].export()
                    elif (cx, cz) in oldchunks:
                        data = oldchunks[cx, cz].export()
                    else:
                        continue
                
                    cnum = cx + cz * RSIZE
                    sectorlength = int(math.ceil((len(data) + 4) / 4096.0))
                    offset = (sectornum << 8) | (sectorlength & 0xff)
                        
                    print 'chunk {0}:'.format((cx, cz)),
                    print 'offset at {0},'.format(cnum * 4),
                    rfile.seek(cnum * 4)
                    rfile.write(struct.pack('>i', offset))
                    
                    print 'mtime at {0},'.format(cnum * 4 + 4096),
                    rfile.seek(cnum * 4 + 4096)
                    rfile.write(struct.pack('>i', int(time.time()) if (cx, cz) in newchunks else self.chunkinfo[cx, cz]['mtime']))
                    
                    print '{0} bytes ({1} sectors) at {2} (sector {3})'.format(len(data), sectorlength, sectornum * 4096, sectornum),
                    rfile.seek(sectornum * 4096)
                    rfile.write(struct.pack('>ib', len(data) + 1, version))
                    rfile.write(data)
                    print
                    
                    sectornum += sectorlength
        
        print 'saved.'


    def _read_chunk_info(self):
        """Returns a dict of chunks that exist in the region file, indexed by coords,
        and containing the modification time and sector offset."""
        rx, rz = self.coords
        chunkinfo = {}
        if os.path.exists(self.path):
            with open(self.path, 'rb') as rfile:
                offsets = struct.unpack('>1024i', rfile.read(4096))
                mtimes = struct.unpack('>1024i', rfile.read(4096))
                for cz in range(RSIZE):
                    for cx in range(RSIZE):
                        index = cx + cz * RSIZE
                        offset = offsets[index]
                        mtime = mtimes[index]
                        if offset > 0:
                            print '{0}: Read header {1} at {2}'.format((cx, cz), hex(offset), ((cx + cz * 32) * 4))
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
        print 'init new region', (rx, rz)
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
            print "{0}: Reading data at sector {1} ({2}), stated length {3}, actual length {4}".format(
                (cx, cz), self.chunkinfo[cx, cz]['sectornum'], self.chunkinfo[cx, cz]['sectornum'] * 4096, length, len(data))
            return AnvilChunk(zlib.decompress(data))

    
    
class Chunk:
    def __init__(self, data):
        self.cheight = 128
        self.tags = nbt.NBTReader().from_string(data)[0][2][0][2]


    def find_tag(self, name, container=None):
        """Find the first tag with the given name."""
        container = container if container is not None else self.tags
        return [tag[2] for tag in container if tag[1] == name][0]
    
    
    def get_heights(self):
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
        self.tags = nbt.NBTReader().from_string(data)[0][2][0][2]
        
        
    def get_data(self, type='block'):
        if type == 'heightmap':
            return self.get_heightmap()
        elif type == 'biome':
            return self.get_biomes()
        else:
            return self.get_blocks()
        
        
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
    
    
    def export(self):
        tags = [('Compound', '', [('Compound', 'Level', self.tags)])]
        return zlib.compress(nbt.NBTWriter().to_string(tags))
        
    

