from PIL import Image, ImageDraw

import map

class ObliqueMap(map.Map):
    def _generate_map_data(self, limits=None):
        """Draw an angled oblique map of this world, within optional n/s/e/w block limits."""
        chunklist = self.world.get_chunk_list(limits)
        n, s, e, w = self._get_extremes(chunklist, self.csize) if limits is None else limits
        
        # the outermost chunks on the map at this rotation
        cext = self._rotate(self._get_diagonal_extremes(chunklist))
        # the outermost blocks within any given chunk
        ccorners = ((0, 0), (0, self.csize - 1), (self.csize - 1, self.csize - 1), (self.csize - 1, 0))
        bext = self._rotate(ccorners)
        # the outermost blocks on the map
        top, left, bottom, right = ((cext[x][0] * self.csize + bext[x][0], cext[x][1] * self.csize + bext[x][1]) for x in range(4))
        
        # diagonal distance between opposite extremes
        width = (abs(right[0] - left[0]) + abs(right[1] - left[1]) + 2)
        height = (abs(bottom[0] - top[0]) + abs(bottom[1] - top[1]) + 2) + self.height - 1
        data = [(0, 0, 0, 0)] * width * height
        
        regions = self.world.get_regions(limits)
        for rnum, (rx, rz) in enumerate(self._order_coords(regions.keys())):
            print 'reading region {0}/{1} {2}...'.format(rnum + 1, len(regions), (rx, rz))
            chunks = regions[rx, rz].read_chunks(chunklist)
            print 'drawing blocks in', len(chunks), 'chunks...'
            for (cx, cz) in self._order_coords(chunks.keys()):
                blocks = chunks[cx, cz].get_blocks()
                for x in range(self.csize) if self.rotate in [0, 1] else reversed(range(self.csize)):
                    for z in range(self.csize) if self.rotate in [0, 3] else reversed(range(self.csize)):
                        bx, bz = cx * self.csize + x, cz * self.csize + z
                        if n <= bx <= s and e <= bz <= w:
                            px, py = self._find_point((bx, bz), left, top)
                            py += self.height # move to bottom block of this column, then draw upward
                            for y in range(self.height):
                                py -= 1
                                if blocks[x][z][y]:
                                    colour = self.colours[blocks[x][z][y]][:4]
                                    #pix[px + pyy * width] = colour # 1 pixel for each block
                                    #pixels = (px, pyy), (px, pyy + 1) # 2 pixels for each block
                                    pixels = (px, py), (px + 1, py), (px, py + 1), (px + 1, py + 1) # 4 pixels for each block
                                    for xx, yy in pixels:
                                        data[xx + yy * width] = self._adjust_colour(self._combine_alpha(colour, data[xx + yy * width]), y)
                                        
        return (width, height), data
        
        
    def _get_diagonal_extremes(self, coords):
        """Given a set of coordinates, return the diagonal extremes
        (northeasternmost, etc)."""
        xrange = [x for (x, z) in coords]
        zrange = [z for (x, z) in coords]
        xmin = min(xrange)
        xmax = max(xrange)
        zmin = min(zrange)
        zmax = max(zrange)

        # i totally forgot how i came up with this bit of magic
        # to do: figure this out and add an explanatory comment
        ne = max((abs(xmax - x + 1) + abs(zmax - z + 1), (x, z)) for (x, z) in coords)[1]
        nw = max((abs(xmax - x + 1) + abs(z - zmin + 1), (x, z)) for (x, z) in coords)[1]
        sw = max((abs(x - xmin + 1) + abs(z - zmin + 1), (x, z)) for (x, z) in coords)[1]
        se = max((abs(x - xmin + 1) + abs(zmax - z + 1), (x, z)) for (x, z) in coords)[1]

        return ne, nw, sw, se
    
    
    def _rotate(self, (a, b, c, d)):
        """Given a set of corners, perform the given a number of clockwise quarter-turns."""
        return (a, b, c, d)[self.rotate:] + (a, b, c, d)[:self.rotate]
    
    
    def _order_coords(self, coords, reverse=False):
        """Order a set of coordinates so that they proceed from back to front,
        according to rotation (or front to back if reverse is true).
        Returns a generator."""
        xrange = sorted(set(x for (x, z) in coords))
        zrange = sorted(set(z for (x, z) in coords))
        
        # xor each condition with boolean 'reverse'... != acts as xor
        return ((x, z)
            for x in (xrange if (self.rotate in [0, 1] != reverse) else reversed(xrange))
                for z in (zrange if (self.rotate in [0, 3] != reverse) else reversed(zrange))
                    if (x, z) in coords)


    def _find_point(self, (x, z), (leftx, leftz), (topx, topz)):
        """Finds the location of an (x, z) point on a grid when tilted diagonally,
        given the diagonal extremes that will be aligned at the top and left of the grid."""
        if self.rotate in [0, 2]:
            px = (x - z) - (leftx - leftz)
            py = (x + z) - (topx + topz)
        else:
            px = (x + z) - (leftx + leftz)
            py = (x - z) - (topx - topz)

        if self.rotate in [1, 2]:
            px = -px
        if self.rotate in [2, 3]:
            py = -py

        return (px, py)

