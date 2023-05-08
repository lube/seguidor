import argparse

import serial
import time
import datetime
import logging
import threading
import re
import dmx
import dmx_mock
import kalman_filter as kf
import uwb_visualizer as uwb_v
import math

TERMINAL_LOGGING = False
PAN_CHANNEL = 10
TILT_CHANNEL = 12


class DWM1001:
    def __init__(self, port="/dev/ttyACM0", baudrate=115200):
        self.ser = serial.Serial(port=port, baudrate=baudrate)
        print(datetime.datetime.now().strftime("%H:%M:%S"), "Connected to " + self.ser.name)

    def send_command(self, command):
        self.ser.write(command.encode())

    def readline(self):
        return self.ser.readline()

    def close(self):
        self.ser.close()

    def read_dwm_messages(self):
        response_lines = []

        while True:
            line = self.readline()
            if not line.decode().endswith("INF] \r\n"):
                decoded_line = line.decode().strip('\r\n')
                log(f"raw la ({decoded_line})")
                response_lines.append(decoded_line)
            else:
                break

        return response_lines


def parse_anchor_positions(response_lines):
    anchor_positions = []

    for line in response_lines:
        match = re.search(r'pos=([\d.-]+):([\d.-]+):([\d.-]+)', line)
        if match:
            x = float(match.group(1))
            y = float(match.group(2))
            z = float(match.group(3))
            anchor_positions.append((x, y, z))

    return anchor_positions


def parse_tag_position(line):
    if line:
        decoded_line = line.decode().strip('\r\n')
        log(decoded_line)
        if len(line) >= 20:
            parse = decoded_line.split(",")
            if parse[0] != "POS" or parse[3] == "nan" or parse[4] == "nan" or parse[5] == "nan":
                return

            return parse[3], parse[4], parse[5]
        else:
            log(f"could not parse {line.decode()}")
    return


def init():
    PAN_SCALE = 1
    PAN_OFFSET = 0

    TILT_SCALE = 1
    TILT_OFFSET = 0

    logging.basicConfig(filename='../uwb_data.log', level=logging.INFO, format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    logging.info("Starting logging...")

    kfx = kf.KalmanFilter(process_variance=1e-4, estimated_measurement_variance=0.1 ** 4)
    kfy = kf.KalmanFilter(process_variance=1e-4, estimated_measurement_variance=0.1 ** 4)
    kfz = kf.KalmanFilter(process_variance=1e-4, estimated_measurement_variance=0.1 ** 4)

    visualizer = uwb_v.UWBVisualizer()

    DWM = DWM1001()

    time.sleep(1)
    DWM.send_command("la\r\r")

    time.sleep(1)
    DWM.send_command("\r\r")

    response_lines = DWM.read_dwm_messages()
    anchor_positions = parse_anchor_positions(response_lines)

    time.sleep(1)
    DWM.send_command("lec\r")

    visualizer.update_anchor_positions(anchor_positions)
    visualizer.load_anchor_colors()

    gui_thread = threading.Thread(target=visualizer.init_visualizer, daemon=True)
    gui_thread.start()
    dmx_interface = dmx_mock.MockDMXInterface()

    while True:
        try:
            line = DWM.readline()
            tag_pos = parse_tag_position(line)
            if tag_pos is None:
                continue
            filter_pos = filter_position(kfx, kfy, kfz, tag_pos)
            visualizer.update_position(filter_pos)
            pan_coarse, pan_fine, tilt_coarse, tilt_fine = uwb_position_to_pan_tilt(filter_pos, PAN_SCALE, PAN_OFFSET, TILT_SCALE, TILT_OFFSET)

            dmx_interface.set_channel(PAN_CHANNEL, pan_coarse)
            dmx_interface.set_channel(PAN_CHANNEL + 1, pan_fine)
            dmx_interface.set_channel(TILT_CHANNEL, tilt_coarse)
            dmx_interface.set_channel(TILT_CHANNEL + 1, tilt_fine)

        except Exception as ex:
            log(f"exception {ex}")
            continue

    DWM.send_command("\r")
    DWM.close()


def filter_position(kfx, kfy, kfz, tag_pos):
    kfx.input_latest_noisy_measurement(float(tag_pos[0]))
    kfy.input_latest_noisy_measurement(float(tag_pos[1]))
    kfz.input_latest_noisy_measurement(float(tag_pos[2]))
    return kfx.get_latest_estimated_measurement(), kfy.get_latest_estimated_measurement(), kfz.get_latest_estimated_measurement()


def log(line):
    if TERMINAL_LOGGING:
        print(datetime.datetime.now().strftime("%H:%M:%S"), line)
    logging.info(line)


def uwb_position_to_pan_tilt(filter_pos, pan_scale, pan_offset, tilt_scale, tilt_offset):
    x, y, z = filter_pos[0], filter_pos[1], filter_pos[2]
    distance = math.sqrt(x ** 2 + y ** 2 + z ** 2)

    pan = math.degrees(math.atan2(y, x)) * pan_scale + pan_offset
    tilt = math.degrees(math.atan2(z, distance)) * tilt_scale + tilt_offset

    pan = max(min(pan, 540), 0)
    tilt = max(min(tilt, 250), 0)

    pan_coarse = int(pan * 65535 / 540)
    pan_fine = int((pan * 65535 / 540 - pan_coarse) * 256)
    tilt_coarse = int(tilt * 65535 / 250)
    tilt_fine = int((tilt * 65535 / 250 - tilt_coarse) * 256)

    return pan_coarse, pan_fine, tilt_coarse, tilt_fine


def send_dmx():
    dmx_i = dmx.DmxPy('/dev/ttyACM1')
    pan_coarse = 45 * 65535 // 540
    pan_fine = int((45 * 65535 / 540 - pan_coarse) * 256)
    tilt_coarse = 45 * 65535 // 250
    tilt_fine = int((45 * 65535 / 250 - tilt_coarse) * 256)

    dmx_i.set_channel(PAN_CHANNEL, pan_coarse)
    dmx_i.set_channel(PAN_CHANNEL + 1, pan_fine)
    dmx_i.set_channel(TILT_CHANNEL, tilt_coarse)
    dmx_i.set_channel(TILT_CHANNEL + 1, tilt_fine)
    dmx_i.render()


def main():
    parser = argparse.ArgumentParser(description="Track positions of a UWB tag and send pan&tilt through a dmx interface")
    parser.add_argument("-s", "--send_dmx", action="store_true", help="Exec dmx send script")

    args = parser.parse_args()

    if args.send_dmx:
        send_dmx()
    else:
        init()


if __name__ == "__main__":
    main()
