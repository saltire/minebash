import argparse

from minebash import obliquemap
from minebash import orthomap
from minebash import world

if __name__ == '__main__':
    argp = argparse.ArgumentParser('Mine Bash - a Minecraft map editor.')
    argp.add_argument('--world', '-w')
    argp.add_argument('--colours', '-c')
    argp.add_argument('--biomes', '-b')
    
    args = argp.parse_args()
    
    wpath = args.world or 'd:\\games\\Minecraft\\server\\loreland' # temp default
    
    wld = world.World(wpath)
    orthomap.OrthoMap(wld, 'colours.csv').draw_map('map-ortho.png')
