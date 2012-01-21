from PIL import Image, ImageDraw

import map

class OrthoMap(map.Map):
    def _generate_map_data(self, rotate=0, limits=None):
        """Draw a top-down map of this world, within optional n/s/e/w block limits.
        Defaults to N at the top. Rotation not implemented yet."""
        chunklist = self.world.get_chunk_list(limits)
        n, s, e, w = self._get_extremes(chunklist, self.csize) if limits is None else limits
        width, height = w - e + 1, s - n + 1

        image = Image.new('RGBA', (width, height))
        pixels = image.load()

        regions = self.world.get_regions(limits)
        for rnum, ((rx, rz), region) in enumerate(sorted(regions.items())):
            print 'reading region {0}/{1} {2}...'.format(rnum + 1, len(regions), (rx, rz))
            chunks = region.read_chunks(chunklist)
            print 'drawing blocks in', len(chunks), 'chunks...'
            for (cx, cz), chunk in chunks.items():
                blocks = chunk.get_blocks()
                for (x, z) in ((x, z) for x in range(self.csize) for z in range(self.csize)):
                    bx, bz = (cx * self.csize + x, cz * self.csize + z)
                    if n <= bx <= s and e <= bz <= w:
                        px, py = w - bz, bx - n
                        for y in reversed(range(self.height)):
                            if blocks[x][z][y]:
                                colour = self._get_block_colour(blocks[x][z], y)
                                pixels[px, py] = colour
                                break
                        
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

