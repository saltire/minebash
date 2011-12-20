from PIL import Image

from minebash import world

class Map:
    def __init__(self, world, colours):
        self.rsize = 32
        self.csize = 16
        self.world = world
        self.colours = self._load_colours(colours)
        
        
    def draw_map(self, imgpath, limits=None):
        """Draw a map of this world, within optional n/s/e/w chunk limits."""
        n, s, e, w = self.world.get_block_edges() if limits is None else limits
        dimensions = (w - e + 1, s - n + 1)
        print n, s, e, w
        print dimensions
        img = Image.new('RGB', dimensions)
        pix = img.load()
        
        regionlist = self._get_coords_in_limits(limits, self.rsize * self.csize) if limits else None
        chunklist = self._get_coords_in_limits(limits, self.csize) if limits else None
        
        regions = self.world.get_regions(regionlist)
        for rnum, ((rx, rz), region) in enumerate(sorted(regions.items())):
            print 'reading region {0}/{1} {2}...'.format(rnum + 1, len(regions), (rx, rz))
            chunks = region.read_chunks(chunklist)
            print 'drawing blocks in', len(chunks), 'chunks...'
            for (cx, cz), chunk in chunks.items():
                cmap = chunk.get_colourmap()
                hmap = chunk.get_heightmap()
                for (x, z) in ((x, z) for x in range(self.csize) for z in range(self.csize)):
                    bx, bz = (cx * self.csize + x, cz * self.csize + z)
                    if n <= bx <= s and e <= bz <= w:
                        pixel = (w - bz, bx - n)
                        colour = self._adjust_colour(self.colours[cmap[x][z]], hmap[x][z])
                        pix[pixel] = colour
                        
        img.save(imgpath)
    
    
    def draw_chunk_map(self, imgpath, limits=None):
        n, s, e, w = self.world.get_chunk_edges()
        dimensions = (w - e + 1, s - n + 1)
        print n, s, e, w
        print dimensions
        img = Image.new('RGB', dimensions)
        pix = img.load()
        
        for (rx, rz), region in sorted(self.world.get_regions().items()):
            print 'reading region', (rx, rz), '...'
            for (cx, cz), chunk in region.read_chunks().items():
                pixel = (w - cz, cx - n)
                pix[pixel] = (255, 255, 255)

        img.save(imgpath)
        
        
    def _load_colours(self, path):
        colours = {}
        with open(path, 'rb') as cfile:
            for line in cfile.readlines():
                if line.strip() and line[:1] != '#':
                    id, r, g, b, a, n = line.split()
                    #colours[int(id)] = (int(r), int(g), int(b), round(int(a) / 255.0, 1), int(n))
                    colours[int(id)] = (int(r), int(g), int(b))
        return colours
    
    
    def _adjust_colour(self, colour, lum):
        return tuple([channel + min(channel, 256 - channel) * (lum - 128) / 256 for channel in colour])
    
    
    def _get_coords_in_limits(self, limits=None, scale=1):
        """Returns all coordinates within a given rectangle,
        defined inclusively by n/s/e/w limits."""
        if limits is None:
            return None
        
        n, s, e, w = limits
        return [(x, z) for x in range(n / scale, s / scale + 1) for z in range(e / scale, w / scale + 1)]
        

