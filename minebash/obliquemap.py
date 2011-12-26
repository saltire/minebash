from PIL import Image

import world

class ObliqueMap:
    def __init__(self, world, colours):
        self.rsize = 32
        self.csize = 16
        self.height = 128
        
        self.world = world
        self.colours = self._load_colours(colours)
        
    
    def draw_map(self, imgpath, rotate=0, limits=None):
        """Draw a diagonal map of this world, within optional n/s/e/w block limits.
        Default rotation has NE at the top, rotate argument = number of clockwise quarter-turns."""
        chunklist = self.world.get_chunk_list(limits)
        cxrange = [cx for (cx, cz) in chunklist]
        czrange = [cz for (cx, cz) in chunklist]
        # highest and lowest values on each axis
        n, s, e, w = (
            min(cxrange) * self.csize,
            max(cxrange) * self.csize + self.csize - 1,
            min(czrange) * self.csize,
            max(czrange) * self.csize + self.csize - 1
            ) if limits is None else limits
        
        # the top and left chunks on the map at this rotation
        cext = self._rotate(self._get_extremes(chunklist), rotate)
        # the top and left blocks within any given chunk
        ccorners = [(0, 0), (0, self.csize - 1), (self.csize - 1, self.csize - 1), (self.csize - 1, 0)]
        bext = self._rotate(ccorners, rotate)
        # the top and left blocks on the map
        top, left, bottom, right = [(cext[x][0] * self.csize + bext[x][0], cext[x][1] * self.csize + bext[x][1]) for x in range(4)]
        
        # diagonal distance between opposite extremes
        width = (abs(right[0] - left[0]) + abs(right[1] - left[1]) + 2)
        height = (abs(bottom[0] - top[0]) + abs(bottom[1] - top[1]) + 2) + self.height - 1
        print (width, height)
        
        img = Image.new('RGB', (width, height))
        pix = img.load()
        
        regions = self.world.get_regions(limits)
        for rnum, (rx, rz) in enumerate(self._order_coords(regions.keys(), rotate)):
            print 'reading region {0}/{1} {2}...'.format(rnum, len(regions), (rx, rz))
            chunks = regions[(rx, rz)].read_chunks(chunklist)
            print 'drawing blocks in', len(chunks), 'chunks...'
            for (cx, cz) in self._order_coords(chunks.keys(), rotate):
                blocks = chunks[(cx, cz)].get_blocks()
                for x in range(self.csize):
                    for z in range(self.csize):
                        bx, bz = cx * self.csize + x, cz * self.csize + z
                        if n <= bx <= s and e <= bz <= w:
                            px, py = self._find_point((bx, bz), left, top, rotate)
                            for y in range(self.height):
                                pixel = px, py + self.height - y - 1
                                if blocks[x][z][y]:
                                    pix[px, py + self.height - y] = self._get_alpha_colour(blocks[x][z], y)
                                    pix[px, py + self.height - y - 1] = self._get_alpha_colour(blocks[x][z], y)
                        
        img.save(imgpath)
        
        
    def _get_extremes(self, coords):
        """Given a set of coordinates, return the diagonal extremes."""
        xrange = [x for (x, z) in coords]
        zrange = [z for (x, z) in coords]
        xmin = min(xrange)
        xmax = max(xrange)
        zmin = min(zrange)
        zmax = max(zrange)

        # i totally forgot how i came up with this bit of magic
        # to do: figure this out and add an explanatory comment
        ne = max([(abs(xmax - x + 1) + abs(zmax - z + 1), (x, z)) for (x, z) in coords])[1]
        nw = max([(abs(xmax - x + 1) + abs(z - zmin + 1), (x, z)) for (x, z) in coords])[1]
        sw = max([(abs(x - xmin + 1) + abs(z - zmin + 1), (x, z)) for (x, z) in coords])[1]
        se = max([(abs(x - xmin + 1) + abs(zmax - z + 1), (x, z)) for (x, z) in coords])[1]

        return ne, nw, sw, se
    
    
    def _rotate(self, (a, b, c, d), rotate):
        """Given a set of corners, perform the given a number of clockwise quarter-turns."""
        return (a, b, c, d)[rotate:] + (a, b, c, d)[:rotate]
    
    
    def _order_coords(self, coords, rotate):
        """Order a set of coordinates so that they proceed from back to front,
        according to rotation."""
        xrange = set([x for (x, z) in coords])
        zrange = set([z for (x, z) in coords])
        return [(x, z)
            for x in (sorted(xrange) if rotate in [0, 1] else reversed(sorted(xrange)))
                for z in (sorted(zrange) if rotate in [0, 3] else reversed(sorted(zrange)))
                    if (x, z) in coords]


    def _find_point(self, (x, z), (leftx, leftz), (topx, topz), rotate):
        """Finds the location of an (x, z) point on a grid when tilted diagonally,
        given the diagonal extremes that will be aligned at the top and left of the grid."""
        if rotate in [0, 2]:
            px = (x - z) - (leftx - leftz)
            py = (x + z) - (topx + topz)
        else:
            px = (x + z) - (leftx + leftz)
            py = (x - z) - (topx - topz)

        if rotate in [1, 2]:
            px = -px
        if rotate in [2, 3]:
            py = -py

        return (px, py)


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


