from unittest.mock import patch, call
from dmx import DmxPy
import dmx as dx


def test_init():
    with patch('serial.Serial', autospec=True) as mock_serial:
        dmx = DmxPy('/dev/ttyUSB0')
        mock_serial.assert_called_once_with('/dev/ttyUSB0', baudrate=57600)
        assert dmx.serial.write.call_count == 2
        assert dmx.serial.write.call_args_list == [call(dx.DMX_OPEN + dx.DMX_INIT1 + dx.DMX_CLOSE),
                                                   call(dx.DMX_OPEN + dx.DMX_INIT2 + dx.DMX_CLOSE)]


def test_set_channel():
    with patch('serial.Serial', autospec=True) as mock_serial:
        dmx = DmxPy('/dev/ttyUSB0')
        dmx.set_channel(1, 255)
        assert dmx.dmxData[1] == bytes([255])


def test_blackout():
    with patch('serial.Serial', autospec=True) as mock_serial:
        dmx = DmxPy('/dev/ttyUSB0')
        dmx.set_channel(1, 255)
        dmx.blackout()
        assert all(channel == bytes([0]) for channel in dmx.dmxData[1:])


def test_update_lighting():
    with patch('serial.Serial', autospec=True) as mock_serial:
        dmx = DmxPy('/dev/ttyUSB0')
        dmx.set_channel(1, 255)
        dmx.update_lighting()
        assert dmx.serial.write.call_count == 3  # two calls in __init__ and one in update_lighting


def test_context_manager():
    with patch('serial.Serial', autospec=True) as mock_serial:
        with DmxPy('/dev/ttyUSB0') as dmx:
            assert dmx.serial is not None

        assert dmx.serial.close.called
