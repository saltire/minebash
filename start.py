import sys

from minebash import obliquemap
from minebash import orthomap
from minebash import world

worldpath = sys.argv[1]
imgpath = sys.argv[2] if len(sys.argv) > 2 else 'map.png'
rotate = sys.argv[3] if len(sys.argv) > 3 else 0
crop = tuple(int(i) for i in sys.argv[4:8]) if len(sys.argv) > 7 else None

print 'world', worldpath
print 'output', imgpath
print 'rotation', rotate
print 'limits', crop

wld = world.World(worldpath)
rotate = 1

#orthomap.OrthoMap(wld, 'colours.csv').draw_map('map-ortho.png')
obliquemap.ObliqueMap(wld, 'colours.csv').set_rotation(rotate).draw_map('map-oblique.png', crop)
