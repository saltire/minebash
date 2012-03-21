from PIL import Image, ImageDraw

import map

class OrthoMap(map.Map):
    def _generate_map_data(self, limits=None):
        """Draw a top-down map of this world, within optional block limits.
        Defaults to N at the top. Rotation not implemented yet."""
        chunklist = self.world.get_chunk_list(limits)
        w, e, n, s = self._get_extremes(chunklist, self.csize) if limits is None else limits
        width, height = e - w + 1, s - n + 1
        
        image = Image.new('RGBA', (width, height))
        pixels = image.load()

        regions = self.world.get_regions(limits)
        for rnum, ((rx, rz), region) in enumerate(sorted(regions.iteritems())):
            print 'reading region {0}/{1} {2}...'.format(rnum + 1, len(regions), (rx, rz))
            chunks = region.read_chunks(chunklist)
            print 'drawing blocks in', len(chunks), 'chunks...'
            for (cx, cz), chunk in chunks.iteritems():
                blocks = chunk.get_blocks()
                for (x, z) in ((x, z) for x in range(self.csize) for z in range(self.csize)):
                    bx, bz = (cx * self.csize + x, cz * self.csize + z)
                    if w <= bx <= e and n <= bz <= s:
                        px, py = bx - w, bz - n
                        for y in reversed(range(self.height)):
                            if blocks[x, z, y]:
                                colour = self._get_block_colour(blocks[x, z, :], y)
                                pixels[px, py] = colour
                                break
                        
        return image
    
    
    def _generate_region_map(self, region, bcrop=None):
        """Generates a map of a region. The drawn blocks may be cropped,
        but the image is always the exact size of a region."""
        size = self.rsize * self.csize
        image = Image.new('RGBA', (size, size))
        pixels = image.load()
        w, e, n, s = bcrop if bcrop else (0, size - 1, 0, size - 1)
        
        chunks = region.read_chunks(bcrop)
        print 'drawing blocks in', len(chunks), 'chunks...'
        for (cx, cz), chunk in chunks.iteritems():
            blocks = chunk.get_blocks()
            for (x, z) in ((x, z) for x in range(self.csize) for z in range(self.csize)):
                bx, bz = (cx * self.csize + x, cz * self.csize + z)
                if w <= bx <= e and n <= bz <= s:
                    for y in reversed(range(self.height)):
                        if blocks[x, z, y]:
                            colour = self._get_block_colour(blocks[x, z, :], y)
                            pixels[bx, bz] = colour
                            break
        return image
    
    
    def _generate_region_heightmap(self, region, bcrop=None):
        size = self.rsize * self.csize
        image = Image.new('RGBA', (size, size))
        pixels = image.load()
        w, e, n, s = bcrop if bcrop else (0, size - 1, 0, size - 1)
        
        chunks = region.read_chunks(bcrop)
        print 'drawing blocks in', len(chunks), 'chunks...'
        for (cx, cz), chunk in chunks.iteritems():
            hmap = chunk.get_heightmap()
            for (x, z) in ((x, z) for x in range(self.csize) for z in range(self.csize)):
                bx, bz = (cx * self.csize + x, cz * self.csize + z)
                if w <= bx <= e and n <= bz <= s:
                    pixels[bx, bz] = [hmap[x, z]] * 3
        return image
                    
        
        
    def _get_block_colour(self, column, y):
        """If a block is partially transparent, combine its colour with that of the block below."""
        top = self.colours[column[y]][:4]
        
        if top[3] < 255:
            bottom = self._get_block_colour(column, y - 1) if y > 0 else (0, 0, 0, 0)
            colour = self._combine_alpha(top, bottom)
        else:
            colour = top
            
        return self._adjust_colour(colour, y)

