from PIL import Image

import world

class Map:
    def __init__(self, world, colours):
        self.rsize = 32
        self.csize = 16
        self.height = 128
        self.rotate = 0
        
        self.world = world
        self.colours = self._load_colours(colours)
        
        
    def draw_map(self, imgpath, limits=None):
        """Gets map data from a subclass method, and saves it to an image file."""
        dimensions, mapdata = self._generate_map_data(limits)
        img = Image.new('RGBA', dimensions)
        img.putdata(mapdata)
        img.save(imgpath)
        print 'saved image to', imgpath
        
    
    def draw_region(self, (rx, rz)):
        """Draw a single region; that is, the data from a single region file."""
        rbsize = self.csize * self.rsize
        crop = rx * rbsize, (rx + 1) * rbsize - 1, rz * rbsize, (rz + 1) * rbsize - 1
        return self.draw_map(crop)
    
    
    def draw_region_at_point(self, (x, z)):
        """Determine which region file holds a certain block, and draw that region."""
        rbsize = self.csize * self.rsize
        rx, rz = x / rbsize, z / rbsize
        return self.draw_region((rx, rz))
        
    
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
        
        
    def set_rotation(self, rotate):
        """Set the number of times to rotate the map a quarter turn clockwise."""
        self.rotate = rotate % 4
        return self
        
        
    def _get_extremes(self, coords, scale=1):
        """Return the highest and lowest values on both axes."""
        xrange = [x for (x, z) in coords]
        zrange = [z for (x, z) in coords]
        return (
            min(xrange) * scale,
            max(xrange) * scale + scale - 1,
            min(zrange) * scale,
            max(zrange) * scale + scale - 1
            )
        
        
    def _load_colours(self, path):
        """Grab block colours from a file."""
        colours = {}
        with open(path, 'rb') as cfile:
            for line in cfile.readlines():
                if line.strip() and line[:1] != '#':
                    id, r, g, b, a, n, name =line.split(',')
                    colours[int(id)] = (int(r), int(g), int(b), int(a), int(n), name.strip())
        return colours

    
    def _adjust_colour(self, colour, lum, amount=1.5, offset=32):
        """Lighten or darken a colour, depending on a luminance value."""
        return tuple(
            int(channel + min(channel, 255 - channel) * (lum - 128 + offset) / 255 * amount)
            for channel in colour[:3]
            ) + colour[3:]
    

    def _combine_alpha(self, (rf, gf, bf, af), (rb, gb, bb, ab), a=255):
        """Composite an RGBA (front) colour on top of an RGB (back) colour.
        Takes an optional alpha argument to apply to the front colour."""
        if af == a == 255:
            return (rf, gf, bf, af)
        af *= a / 255
        return (
            (rf * af + rb * ab * (255 - af) / 255) / 255,
            (gf * af + gb * ab * (255 - af) / 255) / 255,
            (bf * af + bb * ab * (255 - af) / 255) / 255,
            af + ab - af * ab / 255
            )

