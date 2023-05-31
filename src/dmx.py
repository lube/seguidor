import serial
from typing import Union
import logging
import datetime

TERMINAL_LOGGING = False


def log(line):
    if TERMINAL_LOGGING:
        print(datetime.datetime.now().strftime("%H:%M:%S"), line)
    logging.info(line)


DMX_OPEN = bytes([126])
DMX_CLOSE = bytes([231])
DMX_INTENSITY = bytes([6, 1, 2])
DMX_INIT1 = bytes([3, 2, 0, 0, 0])
DMX_INIT2 = bytes([10, 2, 0, 0, 0])


class DmxPy:
    def __init__(self, serial_port: str):
        self.serial = None
        self.dmxData = [bytes([0])] * 513  # 128 plus "spacer".

        try:
            self.serial = serial.Serial(serial_port, baudrate=57600)
            self.serial.write(DMX_OPEN + DMX_INIT1 + DMX_CLOSE)
            self.serial.write(DMX_OPEN + DMX_INIT2 + DMX_CLOSE)
        except Exception as ex:
            print(f"Error: could not open Serial Port, exception: {ex}")
            raise ex

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.serial:
            self.serial.close()

    def set_channel(self, chan: int, intensity: Union[int, bytes]):
        chan = max(0, min(chan, 512))
        intensity = max(0, min(intensity, 255))

        if isinstance(intensity, int):
            intensity = bytes([intensity])

        log(f"setting channel {chan} to value {intensity}")
        self.dmxData[chan] = intensity

    def blackout(self):
        for i in range(1, 512, 1):
            self.dmxData[i] = bytes([0])

    def update_lighting(self):
        sdata = b''.join(self.dmxData)
        self.serial.write(DMX_OPEN + DMX_INTENSITY + sdata + DMX_CLOSE)
        log(f"writing to channels {sdata}")