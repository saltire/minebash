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
        self.regionlist, self.anvil = self._read_region_list(force_region)
        print '{0}: world type is {1}'.format(self.name, 'Anvil' if self.anvil else 'McRegion')

        self.regions = {}
        for rx, rz in self.get_region_list():
            self.regions[rx, rz] = Region(self.path, (rx, rz), self.anvil)
            
            
    def get_chunk_list(self, whitelist=None):
        """Returns a list of global coordinates of all existing chunks,
        within an optional whitelist of global chunk coordinates."""
        return set((rx * RSIZE + cx, rz * RSIZE + cz)
                for (rx, rz), region in self.regions.iteritems()
                    for cx, cz in region.get_chunk_list(whitelist))
    
    
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
            return set((rx, rz) for rx, rz in self.regionlist if (rx, rz) in region_whitelist)
        
        
    def get_regions(self, whitelist=None):
        """Returns a dict of all existing regions, indexed by region coordinates,
        within an optional whitelist of global chunk coordinates."""
        return {(rx, rz): self.regions[rx, rz] for rx, rz in self.get_region_list(whitelist)}
    
    
    def get_region(self, (rx, rz)):
        """Returns a region at a specific coordinate, if it exists."""
        return self.regions[rx, rz] if (rx, rz) in self.regions else None
    
    
    def _read_region_list(self, force_region=0):
        """Returns a list of coordinates of all regions in the world directory,
        and whether the world is in the newer Anvil format or not.
        Setting force_region to true forces it to look for the old region format."""
        anvillist = set()
        regionlist = set()
        regionpath = os.path.join(self.path, 'region')
        if not os.path.isdir(regionpath):
            print "Dir doesn't exist!"
            
        else:
            for filename in os.listdir(regionpath):
                r, rx, rz, ext = filename.split('.')
                if r == 'r' and ext == 'mca':
                    anvillist.add((int(rx), int(rz)))
                elif r == 'r' and ext == 'mcr':
                    regionlist.add((int(rx), int(rz)))
                    
        return (anvillist, True) if anvillist and not force_region else (regionlist, False)
    
    
    
class Region:
    def __init__(self, worldpath, (rx, rz), anvil=True):
        self.path = os.path.join(worldpath, 'region', 'r.{0}.{1}.{2}'.format(rx, rz, 'mca' if anvil else 'mcr'))
        self.coords = rx, rz
        self.chunkinfo = self._read_chunk_info()
        self.anvil = anvil
        
        
    def get_chunk_list(self, whitelist=None):
        """Returns a list of REGIONAL chunk coordinates existing in the region file,
        within an optional whitelist of GLOBAL chunk coordinates."""
        if whitelist is None:
            return self.chunkinfo.keys()
        else:
            rx, rz = self.coords
            return set((cx, cz) for cx, cz in self.chunkinfo.keys()
                    if (rx * RSIZE + cx, rz * RSIZE + cz) in whitelist)
    
    
    def read_chunks(self, whitelist=None):
        """Returns a dict of all chunks in the region, indexed by REGIONAL chunk coordinates,
        within an optional whitelist of GLOBAL chunk coordinates."""
        chunklist = self.get_chunk_list(whitelist)
        if not chunklist or not os.path.exists(self.path):
            return {}
        
        print 'reading', self.path
        with open(self.path, 'rb') as rfile:
            return {(cx, cz): self._read_chunk((cx, cz), rfile)
                    for cz in range(RSIZE) for cx in range(RSIZE) if (cx, cz) in chunklist}
        
        
    def save(self, newchunks={}):
        oldchunks = self.read_chunks()

        if not os.path.exists(os.path.dirname(self.path)):
            os.makedirs(os.path.dirname(self.path))
            
        print 'chunks to save in region {0}: {1} old, {2} new, {3} replaced'.format(
            self.coords, len(oldchunks), len(newchunks), len(set((cx, cz) for cx, cz in oldchunks if (cx, cz) in newchunks)))
        
        with open(self.path, 'wb') as rfile:
            sectornum = 2
            version = 2
            for cz in range(RSIZE):
                for cx in range(RSIZE):
                    if (cx, cz) in newchunks:
                        data = zlib.compress(newchunks[cx, cz].export())
                        print 'new',
                    elif (cx, cz) in oldchunks:
                        data = zlib.compress(oldchunks[cx, cz].export())
                        print 'old',
                    else:
                        continue
                
                    cnum = cx + cz * RSIZE
                    sectorlength = int(math.ceil((len(data) + 4) / 4096.0))
                    offset = (sectornum << 8) | (sectorlength & 0xff)
                    mtime = int(time.time()) if (cx, cz) in newchunks else self.chunkinfo[cx, cz]['mtime']
                    self.chunkinfo[cx, cz] = {'mtime': mtime, 'sectornum': sectornum, 'sectorlength': sectorlength}
                        
                    print 'chunk {0}:'.format((cx, cz)),
                    print 'offset {0} at {1},'.format(hex(offset), hex(cnum * 4)),
                    rfile.seek(cnum * 4)
                    rfile.write(struct.pack('>i', offset))
                    
                    print 'mtime at {0},'.format(hex(cnum * 4 + 4096)),
                    rfile.seek(cnum * 4 + 4096)
                    rfile.write(struct.pack('>i', mtime))
                    
                    print '{0} bytes ({1} sectors) at {2} (sector {3})'.format(len(data), sectorlength, hex(sectornum * 4096), sectornum),
                    rfile.seek(sectornum * 4096)
                    rfile.write(struct.pack('>ib', len(data) + 1, version))
                    rfile.write(data)
                    print
                    
                    sectornum += sectorlength
                    
        print 'saved to', self.path
        print


    def _read_chunk_info(self):
        """Returns a dict of chunks that exist in the region file, indexed by coords,
        and containing the modification time and sector offset."""
        print 'reading header for region', self.coords
        rx, rz = self.coords
        chunkinfo = {}
        if os.path.exists(self.path):
            with open(self.path, 'rb') as rfile:
                offsets = struct.unpack('>1024i', rfile.read(4096))
                mtimes = struct.unpack('>1024i', rfile.read(4096))
                for cz in range(RSIZE):
                    for cx in range(RSIZE):
                        cnum = cx + cz * RSIZE
                        offset = offsets[cnum]
                        mtime = mtimes[cnum]
                        if offset > 0:
                            sectornum = offset / 256 # first sector of chunk (3 bytes)
                            sectorlength = offset % 256 # chunk's length in sectors (1 byte)
                            print '{0}: read offset {1} (sector {2}, {3} sectors) at {4}'.format(
                                (cx, cz), hex(offset), sectornum, sectorlength, hex(cnum * 4))
                            chunkinfo[cx, cz] = {'sectornum': sectornum, 'sectorlength': sectorlength, 'mtime': mtime}
                            
        return chunkinfo
    
    
    def _read_chunk(self, (cx, cz), rfile):
        #print '{0}: reading chunk at sector {1} ({2}),'.format(
        #    (cx, cz), self.chunkinfo[cx, cz]['sectornum'], hex(self.chunkinfo[cx, cz]['sectornum'] * 4096)),
            
        rfile.seek(self.chunkinfo[cx, cz]['sectornum'] * 4096)
        length, version = struct.unpack('>ib', rfile.read(5))
        #print 'stated length {0},'.format(hex(length)),

        # use ONE of the following two lines:
        data = rfile.read(length - 1) # this trusts that the length field is correct
        #data = rfile.read(self.chunkinfo[(cx, cz)]['sectorlength'] * 4096 - 5).rstrip('\x00') # this does not trust the length field
        #print 'data length {0} bytes'.format(len(data))

        if version == 2:
            try:
                return AnvilChunk(zlib.decompress(data)) if self.anvil else Chunk(zlib.decompress(data))
            except zlib.error as error:
                print '\nzlib error with chunk {0}: {1}\n'.format((cx, cz), error)
        else:
            print 'chunk {0}: wrong version {1} at offset {2}'.format((cx, cz), version, hex(self.chunkinfo[cx, cz]['sectornum'] * 4096))
        
        

class Chunk:
    def __init__(self, data):
        self.cheight = 128
        self.tags = nbt.NBTReader().from_string(data)[0][2][0][2]


    def find_tag(self, name, container=None):
        """Find the first tag with the given name."""
        container = container if container is not None else self.tags
        return [tag[2] for tag in container if tag[1] == name][0]
    
    
    def get_data(self, type='block'):
        if type == 'heightmap':
            return self._get_heightmap()
        else:
            return self._get_blocks()
        
        
    def _get_heightmap(self):
        hmapdata = self.find_tag('HeightMap')
        hmap = numpy.zeros((CSIZE, CSIZE), numpy.ubyte) # x, z
        for z in range(CSIZE):
            hmap[:, z] = hmapdata[z * CSIZE:(z + 1) * CSIZE]
        return hmap
    
    
    def _get_blocks(self):
        bdata = self.find_tag('Blocks')
        blocks = numpy.zeros((CSIZE, CSIZE, self.cheight), numpy.uint16) # x, z, y
        for x in range(CSIZE):
            for z in range(CSIZE):
                colstart = x * self.cheight * CSIZE + z * self.cheight
                blocks[x, z, :] = bdata[colstart:colstart + self.cheight]
        return blocks


    def _get_block_data(self):
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
    def __init__(self, data=None):
        self.tags = nbt.NBTReader().from_string(data)[0][2][0][2]

            
    def export(self):
        tags = [('Compound', '', [('Compound', 'Level', self.tags)])]
        return nbt.NBTWriter().to_string(tags)

    
    def get_data(self, type='block', coords=None):
        if type == 'heightmap':
            data = self._get_heightmap()
        elif type == 'biome':
            data = self._get_biomes()
        else:
            data = self._get_blocks()
            
        return data[coords] if coords else data
        
        
    def _get_heightmap(self):
        heightmap = numpy.zeros((CSIZE, CSIZE), numpy.ubyte) # x, z
        hmapdata = self.find_tag('HeightMap')
        for z in range(CSIZE):
            heightmap[:, z] = hmapdata[z * CSIZE:(z + 1) * CSIZE]
        return heightmap
        
    
    def _get_biomes(self):
        biomes = numpy.zeros((CSIZE, CSIZE), numpy.ubyte) # x, z
        bidata = self.find_tag('Biomes')
        for z in range(CSIZE):
            biomes[:, z] = bidata[z * CSIZE:(z + 1) * CSIZE]
        return biomes
            

    def _get_blocks(self):
        blocks = numpy.zeros((CSIZE, CSIZE, SECHEIGHT * SECTIONS), numpy.uint16) # x, z, y
        sections = {}
        for section in (tag[2] for tag in self.find_tag('Sections')[1]):
            sections[self.find_tag('Y', section)] = self.find_tag('Blocks', section)
        for x in range(CSIZE):
            for z in range(CSIZE):
                for s, section in sections.items():
                    sya = s * SECHEIGHT
                    syb = sya + SECHEIGHT
                    start = CSIZE * z + x
                    # get a Y column from data stored in YZX order
                    blocks[x, z, sya:syb] = section[start:start + SECHEIGHT * CSIZE * CSIZE:CSIZE * CSIZE]
        # still have to implement the extra data layer in the anvil format
        return blocks


