from PIL import Image, ImageDraw

import map

class OrthoMap(map.Map):
    def _generate_map(self, type='block', bcrop=None):
        """Generate a single image with a top-down map of this world,
        optionally cropped to a bounding box. North is at the top."""
        if bcrop:
            print 'cropping map to {0} W, {1} E, {2} N, {3} S'.format(*bcrop)
        chunklist = self._crop_coords(self.world.get_chunk_list(), bcrop, self.csize)
        w, e, n, s = self._scale_edges_up(self._get_edges(chunklist), self.csize) if bcrop is None else bcrop

        width, height = e + 1 - w, s + 1 - n
        image = Image.new('RGBA', (width, height))
        
        regions = self.world.get_regions(chunklist)
        for rnum, ((rx, rz), region) in enumerate(sorted(regions.iteritems())):
            print 'reading region {0} of {1} {2}...'.format(rnum + 1, len(regions), (rx, rz))
            bx, bz = rx * self.rsize * self.csize - w, rz * self.rsize * self.csize - n
            image.paste(self._generate_region_map(region, type, (w, e, n, s)), (bx, bz))
            
        return image
        
        
    def _generate_region_map(self, region, type='block', bcrop=None):
        rx, rz = region.coords
        size = self.rsize * self.csize
        w, e, n, s = bcrop or (rx * size, (rx + 1) * size - 1, rz * size, (rz + 1) * size - 1)
        image = Image.new('RGBA', (size, size))
        pixels = image.load()
        
        chunks = region.read_chunks(set((x / self.csize, z / self.csize) for x in range(w, e + 1) for z in range(n, s + 1)))
        print 'drawing {0} chunks...'.format(len(chunks))
        for (cx, cz), chunk in chunks.iteritems():
            data = chunk.get_data(type)
            for (x, z) in ((x, z) for x in range(self.csize) for z in range(self.csize)):
                bx, bz = (cx * self.csize + x, cz * self.csize + z)
                if w <= rx * size + bx <= e and n <= rz * size + bz <= s:
                    pixels[bx, bz] = self._get_colour(type, data[x, z])
        
        return image
    
    
    def _get_colour(self, type, index):
        if type == 'heightmap':
            return (index, index, index)
        elif type == 'biome':
            return self.biomes[index]
        else:
            return self._get_block_colour(index)
                
                
    def _get_block_colour(self, column):
        for y in reversed(range(self.height)):
            if column[y]:
                return self._get_block_column_colour(column, y)
                
                
    def _get_block_column_colour(self, column, y):
        """If a block is partially transparent, combine its colour with that of the block below."""
        top = self.colours[column[y]][:4]
        
        if top[3] < 255:
            bottom = self._get_block_column_colour(column, y - 1) if y > 0 else (0, 0, 0, 0)
            colour = self._combine_alpha(top, bottom)
        else:
            colour = top
            
        return self._adjust_colour(colour, y)

