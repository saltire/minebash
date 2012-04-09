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
        if type_byte == '':
            return None

        type = struct.unpack('>b', type_byte)[0]
        if type == 0:
            return 0

        namelength = struct.unpack('>h', self._read(2))[0]
        name = self._read(namelength)

        return self.types[type], name, self._get_tag_payload(type)


    def _get_tag_payload(self, type):
        """Get the payload of a tag."""
        if type == 1: # byte
            return struct.unpack('>b', self._read(1))[0]

        elif type == 2: # short
            return struct.unpack('>h', self._read(2))[0]

        elif type == 3: # int
            return struct.unpack('>i', self._read(4))[0]

        elif type == 4: # long
            return struct.unpack('>q', self._read(8))[0]

        elif type == 5: # float
            return struct.unpack('>f', self._read(4))[0]

        elif type == 6: # double
            return struct.unpack('>d', self._read(8))[0]

        elif type == 7: # byte array
            length = struct.unpack('>i', self._read(4))[0]
            return struct.unpack('>{0}b'.format(length), self._read(length))

        elif type == 8: # string
            length = struct.unpack('>h', self._read(2))[0]
            #return unicode(file.read(length), 'utf-8')
            return self._read(length)

        elif type == 9: # list
            subtype, length = struct.unpack('>bi', self._read(5))
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
            length = struct.unpack('>i', self._read(4))[0]
            return struct.unpack('>{0}i'.format(length), self._read(length * 4))
        
        
        
class NBTWriter(NBT):
    def to_string(self, tags):
        data = ''
        for tag in tags:
            data = ''.join((data, self._write_tag(*tag)))
            
        return data


    def _write_tag(self, type, name, payload):
        """Get the binary representation of a tag."""
        print type, name
            
        header = struct.pack('>bh{0}b'.format(len(name)), self.types.index(type), len(name), *[ord(x) for x in name])
        return ''.join((header, self._write_tag_payload(self.types.index(type), payload)))
        
        
    def _write_tag_payload(self, type, payload):
        """Get a binary representation of a tag payload."""
        if type == 1: # byte
            return struct.pack('>b', payload)

        elif type == 2: # short
            return struct.pack('>h', payload)

        elif type == 3: # int
            return struct.pack('>i', payload)

        elif type == 4: # long
            return struct.pack('>q', payload)

        elif type == 5: # float
            return struct.pack('>f', payload)

        elif type == 6: # double
            return struct.pack('>d', payload)

        elif type == 7: # byte array
            return struct.pack('>i{0}b'.format(len(payload)), len(payload), *payload)

        elif type == 8: # string
            return struct.pack('>h{0}b'.format(len(payload)), len(payload), *[ord(x) for x in name])

        elif type == 9: # list
            subtype, taglist = payload
            subtype = self.types.index(subtype)
            return ''.join([struct.pack('>bi', subtype, len(taglist))]
                            + [self._write_tag_payload(subtype, tag) for type, name, tag in taglist])

        elif type == 10: # compound
            return ''.join([self._write_tag(*tag) for tag in payload])
            
        elif type == 11: # integer array
            return struct.pack('>i{0}i'.format(len(payload)), len(payload), *payload)
        
        
        
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
