import sys

from minebash import obliquemap
from minebash import orthomap
from minebash import world

worldpath = sys.argv[1]
imgpath = sys.argv[2] if len(sys.argv) > 2 else 'map.png'

wld = world.World(worldpath)

rotate = 1

#orthomap.OrthoMap(wld, 'colours.csv').draw_map('map-ortho.png')
obliquemap.ObliqueMap(wld, 'colours.csv').set_rotation(rotate).draw_map('map-oblique.png')
