from PIL import Image

import world

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
        
        chunklist = self.world.get_chunk_list(limits)
        regions = self.world.get_regions(limits)
        for rnum, ((rx, rz), region) in enumerate(sorted(regions.items())):
            print 'reading region {0}/{1} {2}...'.format(rnum + 1, len(regions), (rx, rz))
            chunks = region.read_chunks(chunklist)
            print 'drawing blocks in', len(chunks), 'chunks...'
            for (cx, cz), chunk in chunks.items():
                blocks = chunk.get_blocks()
                hmap = chunk.get_heightmap()
                for (x, z) in ((x, z) for x in range(self.csize) for z in range(self.csize)):
                    bx, bz = (cx * self.csize + x, cz * self.csize + z)
                    if n <= bx <= s and e <= bz <= w:
                        pixel = (w - bz, bx - n)
                        y = hmap[x][z] - 1
                        colour = self._adjust_colour(self._get_alpha_colour(blocks[x][z], y), y) 
                        #colour = self._adjust_colour(self.colours[blocks[x][z][y]], y) # no alpha
                        pix[pixel] = colour
                        
        img.save(imgpath)
        
        
    def draw_chunk_map(self, imgpath, limits=None):
        """Draws a small map showing all chunks present."""
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
        """Grab block colours from a file."""
        colours = {}
        with open(path, 'rb') as cfile:
            for line in cfile.readlines():
                if line.strip() and line[:1] != '#':
                    id, r, g, b, a, n, name =line.split(',')
                    colours[int(id)] = (int(r), int(g), int(b), float(a), int(n), name.strip())
        return colours
    
    
    def _get_alpha_colour(self, column, height):
        """If a block is partially transparent, combine its colour with that of the block below."""
        r, g, b, a = self.colours[column[height]][:4]
        if a < 1:
            r2, g2, b2 = self._get_alpha_colour(column, height - 1)
            r, g, b = (
                int(r * a + r2 * (1 - a)),
                int(g * a + g2 * (1 - a)),
                int(b * a + b2 * (1 - a))
                )
        return r, g, b
    
    
    def _adjust_colour(self, colour, lum):
        """Lighten or darken a colour, depending on a luminance value."""
        return tuple([channel + min(channel, 256 - channel) * (lum - 128) / 256 for channel in colour[:3]])
    
    
    def _get_coords_in_limits(self, limits=None, scale=1):
        """Returns all coordinates within a given rectangle,
        defined inclusively by n/s/e/w limits."""
        if limits is None:
            return None
        
        n, s, e, w = limits
        return [(x, z) for x in range(n / scale, s / scale + 1) for z in range(e / scale, w / scale + 1)]
        

