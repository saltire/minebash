import gzip
import struct


class NBT:
    types = [
        'End',
        'Byte',
        'Short',
        'Integer',
        'Long',
        'Float',
        'Double',
        'Byte Array',
        'String',
        'List',
        'Compound',
        'Integer Array'
        ]


    
class NBTReader(NBT):
    def from_file(self, path):
        with gzip.open(path) as nbtfile:
            return self.from_string(nbtfile.read())
            

    def from_string(self, data):
        """Fill self.tags with all the tags in the given NBT data string."""
        self.data = data
        self.pointer = 0
        
        tags = []
        while True:
            tag = self._get_next_tag()
            if not tag:
                break
            tags.append(tag)
        return tags


    def _read(self, length):
        """Read a length of data from the original input, starting at the current
        pointer value, and advance the pointer."""
        data = self.data[self.pointer:self.pointer + length]
        self.pointer += length
        return data


    def _get_next_tag(self):
        """Get the next tag in the file. Returns (type, name, payload)."""
        type_byte = self._read(1)
        if type_byte == '': # eof
            return None

        type = struct.unpack('>B', type_byte)[0]
        if type == 0: # end tag
            return 0

        namelength = struct.unpack('>H', self._read(2))[0]
        name = self._read(namelength)

        return self.types[type], name, self._get_tag_payload(type)


    def _get_tag_payload(self, type):
        """Get the payload of a tag."""
        if type == 1: # byte
            return struct.unpack('>B', self._read(1))[0]

        elif type == 2: # short
            return struct.unpack('>H', self._read(2))[0]

        elif type == 3: # int
            return struct.unpack('>I', self._read(4))[0]

        elif type == 4: # long
            return struct.unpack('>Q', self._read(8))[0]

        elif type == 5: # float
            return struct.unpack('>f', self._read(4))[0]

        elif type == 6: # double
            return struct.unpack('>d', self._read(8))[0]

        elif type == 7: # byte array
            length = struct.unpack('>I', self._read(4))[0]
            return struct.unpack('>{0}B'.format(length), self._read(length))

        elif type == 8: # string
            length = struct.unpack('>H', self._read(2))[0]
            #return unicode(file.read(length), 'utf-8')
            return self._read(length)

        elif type == 9: # list
            subtype, length = struct.unpack('>BI', self._read(5))
            taglist = [(self.types[subtype], '', self._get_tag_payload(subtype)) for i in range(length)]
            return self.types[subtype], taglist

        elif type == 10: # compound
            compound = []
            while True:
                tag = self._get_next_tag()
                if tag == 0:
                    break
                compound.append(tag)
            return compound

        elif type == 11: # integer array
            length = struct.unpack('>I', self._read(4))[0]
            return struct.unpack('>{0}I'.format(length), self._read(length * 4))
        
        
        
class NBTWriter(NBT):
    def to_file(self, path, tags):
        with gzip.open(path, 'wb') as nbtfile:
            nbtfile.write(self.to_string(tags))
    
    
    def to_string(self, tags):
        data = ''
        for tag in tags:
            data = ''.join((data, self._write_tag(*tag)))
            
        return data


    def _write_tag(self, type, name, payload):
        """Get the binary representation of a tag."""
        header = struct.pack('>BH{0}B'.format(len(name)), self.types.index(type), len(name), *[ord(x) for x in name])
        return ''.join((header, self._write_tag_payload(self.types.index(type), payload)))
        
        
    def _write_tag_payload(self, type, payload):
        """Get a binary representation of a tag payload."""
        if type == 1: # byte
            return struct.pack('>B', payload)

        elif type == 2: # short
            return struct.pack('>H', payload)

        elif type == 3: # int
            return struct.pack('>I', payload)

        elif type == 4: # long
            return struct.pack('>Q', payload)

        elif type == 5: # float
            return struct.pack('>f', payload)

        elif type == 6: # double
            return struct.pack('>d', payload)

        elif type == 7: # byte array
            return struct.pack('>I{0}B'.format(len(payload)), len(payload), *payload)

        elif type == 8: # string
            return struct.pack('>H{0}B'.format(len(payload)), len(payload), *[ord(x) for x in payload])

        elif type == 9: # list
            subtype, taglist = payload
            subtype = self.types.index(subtype)
            return ''.join([struct.pack('>BI', subtype, len(taglist))]
                            + [self._write_tag_payload(subtype, tag) for type, name, tag in taglist])

        elif type == 10: # compound
            return ''.join([self._write_tag(*tag) for tag in payload] + [struct.pack('>B', 0)])

        elif type == 11: # integer array
            return struct.pack('>I{0}I'.format(len(payload)), len(payload), *payload)
        
        
        
def validate_nbt_data(type, value):
    numerics = {
        'Byte': ('>b', -128, 127),
        'Short': ('>h', -32768, 32767),
        'Integer': ('>i', -2147483648, 2147483647),
        'Long': ('>q', -9223372036854775808, 9223372036854775807),
        'Float': ('>f', 1.40129846432481707e-45, 3.40282346638528860e+38),
        'Double': ('>d', 4.94065645841246544e-324, 1.79769313486231570e+308)
    }

    if type in numerics:
        format, min, max = numerics[type]

        if type in ['Short', 'Integer', 'Long']:
            try:
                value = int(value)
            except ValueError:
                raise ValueError('Not an integer.')

        elif type in ['Float', 'Double']:
            try:
                value = float(double)
            except ValueError:
                raise ValueError('Not a number.')

        if not min <= value <= max:
            raise ValueError('Out of range. Try something from {0} to {1}'.format(min, max))

    return str(value)
