import map

class OrthoMap(map.Map):
    def _generate_map_data(self, rotate=0, limits=None):
        """Draw a top-down map of this world, within optional n/s/e/w block limits.
        Defaults to N at the top. Rotation not implemented yet."""
        chunklist = self.world.get_chunk_list(limits)
        n, s, e, w = self._get_extremes(chunklist, self.csize) if limits is None else limits
        width, height = w - e + 1, s - n + 1
        data = [0] * width * height

        regions = self.world.get_regions(limits)
        for rnum, ((rx, rz), region) in enumerate(sorted(regions.items())):
            print 'reading region {0}/{1} {2}...'.format(rnum + 1, len(regions), (rx, rz))
            chunks = region.read_chunks(chunklist)
            print 'drawing blocks in', len(chunks), 'chunks...'
            for (cx, cz), chunk in chunks.items():
                blocks = chunk.get_blocks()
                #hmap = chunk.get_heightmap()
                for (x, z) in ((x, z) for x in range(self.csize) for z in range(self.csize)):
                    bx, bz = (cx * self.csize + x, cz * self.csize + z)
                    if n <= bx <= s and e <= bz <= w:
                        px, py = w - bz, bx - n
                        #y = hmap[x][z] - 1
                        #colour = self._adjust_colour(self._get_alpha_colour(blocks[x][z], y), y) 
                        #data[px + py * width] = colour
                        for y in reversed(range(self.height)):
                            if blocks[x][z][y]:
                                colour = self._adjust_colour(self._get_alpha_colour(blocks[x][z], y), y)
                                data[px + py * width] = colour
                                break
                        
        return (width, height), data
        
        
    def _adjust_colour(self, colour, lum):
        """Lighten or darken a colour, depending on a luminance value."""
        return tuple([channel + min(channel, 256 - channel) * (lum - 128) / 256 for channel in colour[:3]])
    

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

