import serial

DMX_OPEN = bytes([126])
DMX_CLOSE = bytes([231])
DMX_INTENSITY = bytes([6]) + bytes([1]) + bytes([2])
DMX_INIT1 = bytes([3]) + bytes([2]) + bytes([0]) + bytes([0]) + bytes([0])
DMX_INIT2 = bytes([10]) + bytes([2]) + bytes([0]) + bytes([0]) + bytes([0])


class DmxPy:
    def __init__(self, serial_port):
        try:
            self.serial = serial.Serial(serial_port, baudrate=57600)
        except Exception as ex:
            print(f"Error: could not open Serial Port, exception: {ex}")
            raise ex

        self.serial.write(DMX_OPEN + DMX_INIT1 + DMX_CLOSE)
        self.serial.write(DMX_OPEN + DMX_INIT2 + DMX_CLOSE)

        self.dmxData = [bytes([0])] * 513  # 128 plus "spacer".

    def set_channel(self, chan, intensity):
        if chan > 512:
            chan = 512
        if chan < 0:
            chan = 0
        if intensity > 255:
            intensity = 255
        if intensity < 0:
            intensity = 0
        self.dmxData[chan] = bytes([intensity])

    def blackout(self):
        for i in range(1, 512, 1):
            self.dmxData[i] = bytes([0])

    def render(self):
        sdata = b''.join(self.dmxData)
        self.serial.write(DMX_OPEN + DMX_INTENSITY + sdata + DMX_CLOSE)
