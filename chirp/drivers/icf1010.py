# Copyright 2012 Dan Smith <dsmith@danplanet.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from chirp.drivers import icf
from chirp import chirp_common, util, directory
from chirp import bitwise

mem_format = """
#seekto 0x01C0;
struct {
  bbcd freq[3];
  bbcd txfreq[3];
  u8 tmode;
  u8 rtone;
  u8 ctone;
  u8 power;
  u8 unknown1;
  u8 unknown2;
  u8 unknown3;
  u8 unknown4;
  u8 unknown5;
  u8 unknown6;
  u8 unknown7;
  u8 unknown8;
  u8 unknown9;
  u8 unknown10;
} memory[32];


struct flags {
  u8 empty:1,
     skip:1,
     tmode:2,
     duplex:2,
     unknown2:2;
};

#seekto 0x05A0;
struct {
  char name[8];
} names[32];

#seekto 0x010;
struct flags flags[32];
"""

DUPLEX = ["", "", "-", "+", "split"]
TMODES = ["", "", "Tone", "TSQL"]

ICFTONES = [67.0,69.3,71.0,71.9,74.4,77.0,79.7,82.5,85.4,88.5,
         91.5,94.8,97.4,100.0,103.5,107.2,110.9,114.8,118.8,
         123.0,127.3,131.8,136.5,141.3,146.2,151.4,156.7,
         159.8,162.2,165.5,167.9,171.3,173.8,177.3,179.9,
         183.5,186.2,189.9,192.8,196.6,199.5,203.5,206.5,
         210.7,218.1,225.7,229.1,233.6,241.8,250.3,254.1]


def _get_freq(bcd_array):
    return (int(bcd_array) * 1000 )


def _set_freq(bcd_array, freq):
    bitwise.int_to_bcd(bcd_array, freq / 1000)


def _swap_nibbles(_byte):
   new_byte=((_byte & 0x0F) << 4 | (_byte & 0xF0) >> 4)
   return new_byte


@directory.register
class ICF1010Radio(icf.IcomCloneModeRadio):
    """Icom IC-F1010"""
    VENDOR = "AAA Icom"
    MODEL = "IC-F1010"

    _model = "\x17\x05\x02\x00"
    _memsize = 0x0800
    _endframe = "Icom Inc\x2e"

    _ranges = [(0x0000, 0x07FF, 16)]

    def get_features(self):
        rf = chirp_common.RadioFeatures()
        rf.valid_tmodes = TMODES
        rf.valid_duplexes = DUPLEX
        rf.valid_bands = [(136000000, 155000000),
                          (146000000, 174000000)]
        rf.valid_skips = ["", "1", "2", "3", "4", "5"]
        rf.valid_modes = ["FM"]
        rf.memory_bounds = (0, 31)
        rf.valid_name_length = 8
        rf.valid_characters = chirp_common.CHARSET_UPPER_NUMERIC
        rf.has_dtcs = True
        rf.has_dtcs_polarity = False
        rf.valid_tuning_steps = [5, 10, 12.5, 15, 20, 25, 30, 50, 100]
        rf.has_tuning_step = False
        rf.has_mode = False
        rf.has_bank = False
        return rf

    def process_mmap(self):
        self._memobj = bitwise.parse(mem_format, self._mmap)

    def get_raw_memory(self, number):
        return (str(self._memobj.memory[number]) +
                str(self._memobj.names[number]) +
                str(self._memobj.flags[number]))

    def get_memory(self, number):
        _mem = self._memobj.memory[number]
        _flg = self._memobj.flags[number]
        _name = self._memobj.names[number]

        mem = chirp_common.Memory()
        mem.number = number


        mem.freq = _get_freq(_mem.freq)
        mem.offset = _get_freq(_mem.txfreq)
        mem.duplex = "split"


        if _mem.rtone > 48:
            mem.rtone = ICFTONES[_swap_nibbles(_mem.rtone)]
        else:
            mem.rtone = ICFTONES[_mem.rtone]

        mem.ctone = ICFTONES[_mem.ctone]

        if mem.rtone:
            mem.tmode = "TSQL"

        if _mem.tmode == 0x80:
            mem.tmode = ""

       

       # mem.tmode = TMODES[_flg.tmode]
        mem.skip = _flg.skip and "S" or ""
        if _name.name.get_raw() != "\xFF\xFF\xFF\xFF":
            mem.name = str(_name.name).rstrip()

        return mem

    def set_memory(self, mem):
        _mem = self._memobj.memory[mem.number]
        _flg = self._memobj.flags[mem.number]
        _name = self._memobj.names[mem.number]

        if mem.empty:
            _flg.empty = True
            return

        #_mem.set_raw("\x00" * 8)
        _flg.set_raw("\x00")

        _set_freq(_mem.freq, mem.freq)
        _set_freq(_mem.txfreq, mem.offset)
        _mem.rtone = ICFTONES.index(mem.rtone)
        _mem.ctone = ICFTONES.index(mem.ctone)
        _flg.duplex = DUPLEX.index(mem.duplex)
        _flg.tmode = TMODES.index(mem.tmode)
        _flg.skip = mem.skip == "S"

        if mem.name:
            _name.name = mem.name.ljust(8)
        else:
            _name.name = "\xFF\xFF\xFF\xFF"
