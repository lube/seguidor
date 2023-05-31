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

CAM_X, CAM_Y, CAM_Z = 1, 1, 1

PAN_SCALE = 1
PAN_OFFSET = 0

TILT_SCALE = 1
TILT_OFFSET = 0

LIGHT_SYSTEMS = {
    "BadBoy": {
        "pan_range": (0, 615),
        "tilt_range": (0, 260),
        "pan_dmx_range": (0, 65535),
        "tilt_dmx_range": (0, 65535),
        "pan_channel": 2,
        "pan_fine_channel": 3,
        "tilt_channel": 4,
        "tilt_fine_channel": 5
    },
    "Sparky": {
        "pan_range": (0, 540),
        "tilt_range": (0, 250),
        "pan_dmx_range": (0, 65535),
        "tilt_dmx_range": (0, 65535),
        "pan_channel": 10,
        "pan_fine_channel": 11,
        "tilt_channel": 12,
        "tilt_fine_channel": 13
    }
}


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


def init(uwb_port, light_port, light_system, use_dmx_mock=False):
    if light_system not in LIGHT_SYSTEMS:
        raise ValueError(f"Unknown light system '{light_system}'. Please select from {list(LIGHT_SYSTEMS.keys())}")

    SELECTED_SYSTEM = light_system

    kfx = kf.KalmanFilter(process_variance=1e-4, estimated_measurement_variance=0.1 ** 4)
    kfy = kf.KalmanFilter(process_variance=1e-4, estimated_measurement_variance=0.1 ** 4)
    kfz = kf.KalmanFilter(process_variance=1e-4, estimated_measurement_variance=0.1 ** 4)

    visualizer = uwb_v.UWBVisualizer()

    DWM = DWM1001(port=uwb_port)

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
    if use_dmx_mock:
        dmx_interface = dmx_mock.MockDMXInterface()
    else:
        dmx_interface = dmx.DmxPy(light_port)

    while True:
        try:
            line = DWM.readline()
            tag_pos = parse_tag_position(line)
            if tag_pos is None:
                continue
            filter_pos = filter_position(kfx, kfy, kfz, tag_pos)
            visualizer.update_position(filter_pos)
            relative_pos = (filter_pos[0] - CAM_X, filter_pos[1] - CAM_Y, filter_pos[2] - CAM_Z)

            pan_coarse, pan_fine, tilt_coarse, tilt_fine = uwb_position_to_pan_tilt(relative_pos, PAN_SCALE, PAN_OFFSET,
                                                                                    TILT_SCALE, TILT_OFFSET,
                                                                                    LIGHT_SYSTEMS[SELECTED_SYSTEM])

            dmx_interface.set_channel(LIGHT_SYSTEMS[SELECTED_SYSTEM]["pan_channel"], pan_coarse)
            dmx_interface.set_channel(LIGHT_SYSTEMS[SELECTED_SYSTEM]["pan_fine_channel"], pan_fine)
            dmx_interface.set_channel(LIGHT_SYSTEMS[SELECTED_SYSTEM]["tilt_channel"], tilt_coarse)
            dmx_interface.set_channel(LIGHT_SYSTEMS[SELECTED_SYSTEM]["tilt_fine_channel"], tilt_fine)

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


def calculate_distance(x, y, z):
    return math.sqrt(x ** 2 + y ** 2 + z ** 2)


def calculate_pan(x, y, pan_scale, pan_offset):
    return math.degrees(math.atan2(y, x)) * pan_scale + pan_offset


def calculate_tilt(z, distance, tilt_scale, tilt_offset):
    return math.degrees(math.atan2(z, distance)) * tilt_scale + tilt_offset


def calculate_dmx_value(angle, max_angle, dmx_range):
    return int(angle * dmx_range / max_angle)


def calculate_fine_dmx_value(angle, max_angle, coarse_value, dmx_range):
    return int((angle * dmx_range / max_angle - coarse_value) * 256)


def uwb_position_to_pan_tilt(filter_pos, pan_scale, pan_offset, tilt_scale, tilt_offset, sel_light_system):
    x, y, z = filter_pos
    distance = calculate_distance(x, y, z)

    pan = calculate_pan(x, y, pan_scale, pan_offset)
    tilt = calculate_tilt(z, distance, tilt_scale, tilt_offset)

    pan_range = sel_light_system["pan_range"]
    tilt_range = sel_light_system["tilt_range"]
    pan_dmx_range = sel_light_system["pan_dmx_range"]
    tilt_dmx_range = sel_light_system["tilt_dmx_range"]

    pan = max(min(pan, pan_range[1]), pan_range[0])
    tilt = max(min(tilt, tilt_range[1]), tilt_range[0])

    log(f"pan: {pan}, tilt: {tilt}")

    pan_coarse, pan_fine, tilt_coarse, tilt_fine = get_pan_and_tilt(pan, pan_dmx_range, pan_range, tilt, tilt_dmx_range,
                                                                    tilt_range)

    return pan_coarse, pan_fine, tilt_coarse, tilt_fine


def send_dmx(light_system, dmx_port):
    if light_system not in LIGHT_SYSTEMS:
        raise ValueError(f"Unknown light system '{light_system}'. Please select from {list(LIGHT_SYSTEMS.keys())}")
    sel_light_system = LIGHT_SYSTEMS[light_system]

    dmx_i = dmx.DmxPy(dmx_port)

    pan_range = sel_light_system["pan_range"]
    tilt_range = sel_light_system["tilt_range"]
    pan_dmx_range = sel_light_system["pan_dmx_range"]
    tilt_dmx_range = sel_light_system["tilt_dmx_range"]

    pan = max(min(0, pan_range[1]), pan_range[0])
    tilt = max(min(0, tilt_range[1]), tilt_range[0])

    pan_coarse, pan_fine, tilt_coarse, tilt_fine = get_pan_and_tilt(pan, pan_dmx_range, pan_range, tilt, tilt_dmx_range,
                                                                    tilt_range)

    log(f"sending test dmx values over channels: c: {LIGHT_SYSTEMS[light_system]['pan_channel']}: pan coarse: {pan_coarse}, "
        f" {LIGHT_SYSTEMS[light_system]['pan_fine_channel']}: pan fine: {pan_fine}, "
        f" {LIGHT_SYSTEMS[light_system]['tilt_channel']}: tilt coarse: {tilt_coarse}, "
        f" {LIGHT_SYSTEMS[light_system]['tilt_fine_channel']}: tilt fine: {tilt_fine}")

    dmx_i.set_channel(LIGHT_SYSTEMS[light_system]["pan_channel"], pan_coarse)
    dmx_i.set_channel(LIGHT_SYSTEMS[light_system]["pan_fine_channel"], pan_fine)
    dmx_i.set_channel(LIGHT_SYSTEMS[light_system]["tilt_channel"], tilt_coarse)
    dmx_i.set_channel(LIGHT_SYSTEMS[light_system]["tilt_fine_channel"], tilt_fine)
    dmx_i.update_lighting()


def get_pan_and_tilt(pan, pan_dmx_range, pan_range, tilt, tilt_dmx_range, tilt_range):
    pan_coarse = calculate_dmx_value(pan, pan_range[1], pan_dmx_range[1])
    pan_fine = calculate_fine_dmx_value(pan, pan_range[1], pan_coarse, pan_dmx_range[1])
    tilt_coarse = calculate_dmx_value(tilt, tilt_range[1], tilt_dmx_range[1])
    tilt_fine = calculate_fine_dmx_value(tilt, tilt_range[1], tilt_coarse, tilt_dmx_range[1])
    return pan_coarse, pan_fine, tilt_coarse, tilt_fine


def main():

    logging.basicConfig(filename='../uwb_data.log', level=logging.INFO, format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    logging.info("Starting logging...")

    parser = argparse.ArgumentParser(description="Track positions of a UWB tag and send pan&tilt through a dmx interface")
    parser.add_argument("-s", "--send_dmx", action="store_true", help="Exec dmx send script")
    parser.add_argument("-dm", "--use-dmx-mock", action="store_true", help="Use DMX mock interface")
    parser.add_argument("-dp", "--dmx-port", default="/dev/ttyUSB0", help="Serial port for light interface (DMX)")
    parser.add_argument("-up", "--uwb-port", default="/dev/ttyACM0", help="Serial port for UWB Positioning (DWM1000)")
    parser.add_argument("-l", "--light_system", default="BadBoy", help="Light system")

    args = parser.parse_args()

    log(f"Starting UWB Positioning and DMX interface with args: {args}")

    if args.send_dmx:
        send_dmx(light_system=args.light_system, dmx_port=args.dmx_port)
    else:
        init(uwb_port=args.uwb_port, light_port=args.dmx_port, light_system=args.light_system,
             use_dmx_mock=args.use_dmx_mock)


if __name__ == "__main__":
    main()
