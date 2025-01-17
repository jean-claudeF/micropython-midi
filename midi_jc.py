# Copyright (C) 2014 Craig Barnes
# Modifications for Micropython by jean-claude.feltes@education.lu
# for Standard Micropython
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

"""
Micro Python Midi

This module implements channel commands according to the midi specification.

Each midi message consists of 3 bytes.

The first byte is the sum of the command and the midi channel (1-16 > 0-F).
the value of bytes 2 and 3 (data 1 and 2) are dependant on the command.

command     data1               data2                  Description
-------     -----                   -----                  -----------
0x80   Key # (0-127)           Off Velocity (0-127)   Note Off
0x90   Key # (0-127)           On Velocity (0-127)    Note On
0xA0   Key # (0-127)           Pressure (0-127)       Poly Pressure
0xB0   Control # (0-127)       Control Value (0-127)  Control
0xC0   Program # (0-127)       Not Used (send 0)      Program Change
0xD0   Pressure Value (0-127)  Not Used (send 0)      Channel Pressure
0xE0   Range LSB (0-127)       Range MSB (0-127)      Pitch Bend

http://www.midi.org/techspecs/midimessages.php
"""
import struct

class MidiInteger:
    """A midi message sends data as 7 bit values between 0 and 127."""
    def __init__(self, value):
        if 0 <= value < 2 ** 7:
            self.value = value
        else:
            raise ValueError(
                'Invalid midi data value: {}'.format(value),
                'A midi data value must be an integer between 0 and 127')

    def __repr__(self):
        return '<MidiInteger: {}>'.format(self.value)


class BigMidiInteger:
    """Some messages use 14 bit values, these need to be spit down to
    msb and lsb before being sent."""
    def __init__(self, value):
        if 0 <= value <= 2 ** 14:
            self.msb = value // 2 ** 7
            self.lsb = value % 2 ** 7
        else:
            raise ValueError(
                'Invalid midi data value: {}'.format(value),
                'A midi datavalue must be an integer between0'
                ' and {}'.format(2 ** 14))

    def __repr__(self):
        return '<BigMidiInteger: lsb={}, msb={}>'.format(self.lsb, self.msb)


class Controller:
    """A device that is designed to send midi messages to an external
    instrument or sequencer, is commonly referred to as a midi controller.
    http://en.wikipedia.org/wiki/MIDI_controller

    An instance of the Controller class should be considered to be a midi
    contoller in the same context.

    More than one can be created, there are no constraints. but the
    convention is to keep each controller on a separate midi port or channel.

    Usage
    =====
    The following example creates a controller on midi channel one using the
    Com Port TX1.  Then sends a note on message followed by a
    note off message.

        >>> from machine import UART
        >>> midi = machine.UART(1, baudrate=31250)
        >>> my_controller = Controller(midi, channel=1)
        >>> my_controller.note_on(65)
        >>> pyb.delay(100)
        >>> my_controller.note_off(65)
    """
    COMMANDS = (
        0x80,  # Note Off
        0x90,  # Note On
        0xA0,  # Poly Pressure
        0xB0,  # Control Change
        0xC0,  # Program Change
        0xD0,  # Mono Pressure
        0xE0   # Pitch Bend
    )

    def __init__(self, port, channel=1):
        self.port = port
        try:
            assert 1 <= channel <= 16
        except:
            raise ValueError('channel must be an integer between 1 & 16')
        self.channel = channel
        self.timeout = 100

    def __repr__(self):
        return '<Controller: port: {port} channel: {channel}>'.format(
            port=self.port,
            channel=self.channel)

    def send_message(self, command, data1, data2=0):
        """Send a midi message to the serial device."""
        # This is changed by JCF
        if command not in self.COMMANDS:
            raise ValueError('Invalid Command: {}'.format(command))

        command += self.channel - 1
        self.port.write(struct.pack("bbb",command, data1, data2))
    
    def note_off(self, note, velocity=0):
        """Send a 'Note Off'  message"""
        self.send_message(0x80, note, velocity)

    def note_on(self, note, velocity=127):
        """Send a 'Note On' message"""
        self.send_message(0x90, note, velocity)

    def pressure(self, value, note=None):
        """If a note value is provided then send a polyphonic pressure
        message, otherwise send a Channel (mono) pressure message."""
        if note:
            self.send_message(0xA0, note, value)
        else:
            self.send_message(0xD0, value)

    def control_change(self, control, value):
        """Send a control e.g. modulation or pedal message."""
        self.send_message(0xB0, control, value)
    '''
    def program_change(self, value, bank=None):
        """Send a program change message, include bank if provided."""
        if bank:
            bank = BigMidiInteger(bank)
            self.control_change(32, bank.lsb)
            self.control_change(0, bank.msb)
        self.send_message(0xC0, value)
    '''
    def program_change(self, value):
        """Send a program change message"""
        command = 0xC0 + self.channel - 1
        self.port.write(struct.pack("bb",command, value))
        

    def pitch_bend(self, value=0x2000):
        """Send a pich bend message.
        Pich bend is a 14 bit value, centreed at 0x2000"""
        value = BigMidiInteger(value)
        self.send_message(0xE0, value.lsb, value.msb)

    def modulation(self, value, fine=False):
        """Send modulation control change."""
        if fine:
            value = MidiInteger(value)
            self.control_change(33, value.lsb)
            self.control_change(1, value.msb)
        else:
            self.control_change(1, value)

    def volume(self, value, fine=False):
        """Send volume control change."""
        if fine:
            value = BigMidiInteger(value)
            self.control_change(39, value.lsb)
            self.control_change(7, value.msb)
        else:
            self.control_change(7, value)

    def all_sound_off(self):
        """Switch all sounds off. """
        self.control_change(120, 0)

    def reset_all_controllers(self):
        """Set all controllers to their default values."""
        self.control_change(121, 0)

    def local_control(self, value):
        """Enable or disable local control."""
        if bool(value):
            self.control_change(122, 127)
        else:
            self.control_change(122, 0)

    def all_notes_off(self):
        """Send 'All Notes Off' message."""
        self.control_change(123, 0)

    def panic(self):
        """Reset everything and stop making noise."""
        self.all_sound_off()
        self.reset_all_controllers()
        self.all_notes_off()
#----------------------------------------------------------------
MINOR_SECOND = 1
SECOND = 2
MINOR_THIRD = 3
THIRD = 4
FOURTH = 5
DIM_FIFTH = 6
FIFTH = 7
MINOR_SIXTH = 8
SIXTH = 9
MINOR_SEVENTH = 10
MAJOR_SEVENTH = 11
OCTAVE = 12






def transpose(notes, interval):
    tnotes = [note + interval for note in notes]
    return tnotes

def playnotes(notes, instrument, ontime, offtime, velocity = 80):
    
    for note in notes:

        print(note)    
        instrument.note_on(note, velocity)
        time.sleep(ontime)
        instrument.note_off(note )
        time.sleep(offtime)


def chord(note, instrument, mode = "MAJOR", duration = 0.2):
    pass

#------------------------------------------------------------------
if __name__ == '__main__':
   
    import time
    from machine import UART
    midi = machine.UART(1, baudrate=31250)
    inst = Controller(midi, channel=1)
   
    notes = [48, 52, 55, 57, 58, 57, 55, 52]
    
    notes4 = transpose(notes, FOURTH)
    notes5 = transpose(notes, FIFTH)
    
        
    inst.program_change(1)
    
    all_notes = notes *2 + notes4 * 2 + notes *2 + notes5 + notes4 + notes *2 + notes5  + notes *2
    all_notes = transpose(all_notes, - OCTAVE)
    
    all_notes = transpose(all_notes, THIRD)
    
    playnotes(all_notes, inst, 0.5, 0)
    
    