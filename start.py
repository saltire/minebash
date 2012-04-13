import argparse

from minebash import obliquemap
from minebash import orthomap
from minebash import world

if __name__ == '__main__':
    argp = argparse.ArgumentParser('Mine Bash - a Minecraft map editor.')
    argp.add_argument('--world', '-w')
    argp.add_argument('--colours', '-c')
    argp.add_argument('--biomes', '-b')
    argp.add_argument('--output', '-o')
    argp.add_argument('--type', '-t')
    
    args = argp.parse_args()
    
    orthomap.OrthoMap(world.World(args.world), args.colours, args.biomes).draw_map(args.output, args.type)
