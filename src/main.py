import serial
import time
import datetime
import logging
import tkinter as tk
import threading
import re
import json
import math

TERMINAL_LOGGING = False
SCALING_CANVAS = 50
OFFSET_CANVAS_X = 50
OFFSET_CANVAS_Y = 50

WIDTH_EXT = 700
WIDTH_INN = 650
HEIGHT_EXT = 300
HEIGHT_INN = 250


# Rotates a point counterclockwise by a given angle around a given origin.
def rotate(point, origin, angle):
    """Rotate a point counterclockwise by a given angle around a given origin.
    The angle should be given in radians.
    """
    ox, oy = origin
    px, py = point

    qx = ox + math.cos(angle) * (px - ox) - math.sin(angle) * (py - oy)
    qy = oy + math.sin(angle) * (px - ox) + math.cos(angle) * (py - oy)

    return qx, qy


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


colors = ["blue", "green", "orange", "red"]


def flip_x(point, center):
    return 2 * center[0] - point[0], point[1]


class KalmanFilter:
    def __init__(self, process_variance, estimated_measurement_variance):
        self.process_variance = process_variance
        self.estimated_measurement_variance = estimated_measurement_variance
        self.posteri_estimate = 0.0
        self.posteri_error_estimate = 1.0

    def input_latest_noisy_measurement(self, measurement):
        priori_estimate = self.posteri_estimate
        priori_error_estimate = self.posteri_error_estimate + self.process_variance

        blending_factor = priori_error_estimate / (priori_error_estimate + self.estimated_measurement_variance)
        self.posteri_estimate = priori_estimate + blending_factor * (measurement - priori_estimate)
        self.posteri_error_estimate = (1 - blending_factor) * priori_error_estimate

    def get_latest_estimated_measurement(self):
        return self.posteri_estimate


class UWBVisualizer:
    def __init__(self):
        self.x_filtered = 0
        self.y_filtered = 0
        self.z_filtered = 0
        self.dot_radius = 25
        self.anchor_positions = []
        self.anchor_colors = [0] * len(self.anchor_positions)
        self.rotation_angle = 90
        self.offset_x = 0
        self.offset_y = 0
        self.scale = 0

    def save_anchor_colors(self, filename):
        with open(filename, "w") as outfile:
            json.dump(self.anchor_colors, outfile)

    def save_ui_configs(self, filename):
        with open(filename, "w") as outfile:
            json.dump([self.offset_x, self.offset_y, self.scale, self.rotation_angle], outfile)

    def load_anchor_colors(self, filename):
        try:
            with open(filename, "r") as infile:
                self.anchor_colors = json.load(infile)
        except FileNotFoundError:
            print(f"No previous anchor colors found. Using default colors.")

    def load_ui_configs(self, filename):
        try:
            with open(filename, "r") as infile:
                [self.offset_x, self.offset_y, self.scale, self.rotation_angle] = json.load(infile)
        except FileNotFoundError:
            print(f"No previous ui found. Using default params.")

    def toggle_anchor_color(self, anchor_index):
        self.anchor_colors[anchor_index] = (self.anchor_colors[anchor_index] + 1) % 4
        self.save_anchor_colors("anchor_colors.json")

    def on_anchor_click(self, event, anchor_index):
        self.toggle_anchor_color(anchor_index)

    def update_position(self, x, y, z):
        self.x_filtered = x
        self.y_filtered = y
        self.z_filtered = z

    def update_anchor_positions(self, anchor_positions):
        self.anchor_positions = anchor_positions
        self.anchor_colors = [0] * len(self.anchor_positions)

    def init_visualizer(self):
        def on_closing():
            root.destroy()

        root = tk.Tk()
        root.protocol("WM_DELETE_WINDOW", on_closing)
        root.title("UWB Position Visualizer")
        frame = tk.Frame(root, width=WIDTH_EXT, height=HEIGHT_EXT)
        frame.pack_propagate(False)  # Prevent the frame to resize to its content
        frame.pack()

        canvas = tk.Canvas(frame, width=WIDTH_INN, height=HEIGHT_INN, bg="white")
        canvas.pack()

        position_label = tk.Label(root, text="Position: (0.00, 0.00, 0.00)", font=("Arial", 13))
        position_label.pack()

        control_frame = tk.Frame(root)
        control_frame.pack(side="top", pady=20)
        control_frame.pack(side="bottom", pady=20)
        control_frame.pack(side="left", padx=20)
        control_frame.pack(side="right", padx=20)

        self.load_ui_configs("ui.json")

        def rotate_all():
            self.rotation_angle += math.radians(10)

        offset_x_slider = tk.Scale(control_frame, from_=-200, to=200, resolution=20, orient="horizontal", label="Offset X",
                                  length=200)
        offset_x_slider.set(self.offset_x)  # Set the initial value to the current offset
        offset_x_slider.pack()
        offset_x_slider.pack(side="left", padx=5)  # Add some padding for spacing

        offset_y_slider = tk.Scale(control_frame, from_=-100, to=100, resolution=20, orient="horizontal", label="Offset Y",
                                  length=200)
        offset_y_slider.set(self.offset_y)  # Set the initial value to the current offset
        offset_y_slider.pack()
        offset_y_slider.pack(side="left", padx=5)  # Add some padding for spacing

        scale_slider = tk.Scale(control_frame, from_=10, to=200, resolution=10, orient="horizontal", label="Scaling",
                                 length=200)
        scale_slider.set(self.scale)  # Set the initial value to the current scaling
        scale_slider.pack()
        scale_slider.pack(side="left", padx=5)  # Add some padding for spacing

        button = tk.Button(control_frame, text="Rotate", command=rotate_all)
        button.pack()

        def update():
            center = (canvas.winfo_width() / 2, canvas.winfo_height() / 2)
            dirty = False
            if self.offset_x != offset_x_slider.get():
                self.offset_x = offset_x_slider.get()
                dirty = True
            if self.offset_y != offset_y_slider.get():
                self.offset_y = offset_y_slider.get()
                dirty = True
            if self.scale != scale_slider.get():
                self.scale = scale_slider.get()
                dirty = True

            if dirty:
                self.save_ui_configs("ui.json")

            x_rot, y_rot = rotate((self.x_filtered, self.y_filtered), (0, 0), self.rotation_angle)

            # Scale and offset the positions for better visualization on the canvas
            x = (x_rot * self.scale + canvas.winfo_width() / 2) - self.offset_x
            y = (y_rot * self.scale + canvas.winfo_height() / 2) - self.offset_y
            (x, y) = flip_x((x, y), center)

            # Clear the canvas and draw a new dot
            canvas.delete("all")
            canvas.create_oval(x - self.dot_radius, y - self.dot_radius, x + self.dot_radius, y + self.dot_radius,
                               fill="red")

            # Draw anchor positions as blue dots
            for index, (x, y, z) in enumerate(self.anchor_positions):
                x_rot, y_rot = rotate((x, y), (0, 0), self.rotation_angle)
                x = (x_rot * self.scale + canvas.winfo_width() / 2) - self.offset_x
                y = (y_rot * self.scale + canvas.winfo_height() / 2) - self.offset_y
                (x, y) = flip_x((x, y), center)

                anchor = canvas.create_oval(x - self.dot_radius, y - self.dot_radius,
                                            x + self.dot_radius, y + self.dot_radius,
                                            fill=colors[self.anchor_colors[index]])
                canvas.tag_bind(anchor, "<Button-1>",
                                lambda event, anchor_index=index: self.on_anchor_click(event,
                                                                                       anchor_index=anchor_index))

            position_label.config(
                text=f"Position: ({self.x_filtered:.2f}, {self.y_filtered:.2f}, {self.z_filtered:.2f})")
            root.after(100, update)

        update()
        root.mainloop()


def init_logger():
    logging.basicConfig(filename='uwb_data.log', level=logging.INFO, format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    logging.info("Starting logging...")

def init():
    init_logger()

    DWM = serial.Serial(port="/dev/ttyACM0", baudrate=115200)
    print("Connected to " + DWM.name)
    time.sleep(1)
    DWM.write("la\r\r".encode())
    time.sleep(1)
    response_lines = []
    print(datetime.datetime.now().strftime("%H:%M:%S"), "start")

    # Read the response lines
    while True:
        line = DWM.readline()
        if not line.decode().endswith("INF] \r\n"):
            decoded_line = line.decode().strip('\r\n')
            log_message = f"raw la ({decoded_line})"
            if TERMINAL_LOGGING:
                print(datetime.datetime.now().strftime("%H:%M:%S"), log_message)
            logging.info(log_message)
            response_lines.append(decoded_line)
        else:
            break

    print(datetime.datetime.now().strftime("%H:%M:%S"), "lec")
    # Parse anchor positions and update the visualizer
    anchor_positions = parse_anchor_positions(response_lines)

    print(datetime.datetime.now().strftime("%H:%M:%S"), "lec")
    DWM.write("lec\r".encode())
    time.sleep(1)

    kfx = KalmanFilter(process_variance=1e-4, estimated_measurement_variance=0.1**4)
    kfy = KalmanFilter(process_variance=1e-4, estimated_measurement_variance=0.1**4)
    kfz = KalmanFilter(process_variance=1e-4, estimated_measurement_variance=0.1**4)

    visualizer = UWBVisualizer()
    visualizer.update_anchor_positions(anchor_positions)
    visualizer.load_anchor_colors("anchor_colors.json")

    gui_thread = threading.Thread(target=visualizer.init_visualizer, daemon=True)
    gui_thread.start()

    while True:
        try:
            line = DWM.readline()
            if line:
                decoded_line = line.decode().strip('\r\n')
                log_message = f"raw lec ({decoded_line})"
                if TERMINAL_LOGGING:
                    print(datetime.datetime.now().strftime("%H:%M:%S"), log_message)
                logging.info(log_message)
                if len(line) >= 20:
                    parse = decoded_line.split(",")
                    if parse[0] != "POS" or parse[3] == "nan" or parse[4] == "nan" or parse[5] == "nan":
                        continue
                    x_pos = float(parse[3])
                    y_pos = float(parse[4])
                    z_pos = float(parse[5])

                    kfx.input_latest_noisy_measurement(float(x_pos))
                    x_filtered = kfx.get_latest_estimated_measurement()
                    kfy.input_latest_noisy_measurement(float(y_pos))
                    y_filtered = kfy.get_latest_estimated_measurement()
                    kfz.input_latest_noisy_measurement(float(z_pos))
                    z_filtered = kfz.get_latest_estimated_measurement()
                    visualizer.update_position(x_filtered, y_filtered, z_filtered)

                    log_message = f"({x_filtered:.2f}, {y_filtered:.2f}, {z_filtered:.2f})"
                    if TERMINAL_LOGGING:
                        print(datetime.datetime.now().strftime("%H:%M:%S"), log_message)
                    logging.info(log_message)
                else:
                    log_message = f"could not parse {line.decode()}"
                    if TERMINAL_LOGGING:
                        print(datetime.datetime.now().strftime("%H:%M:%S"), log_message)
                    logging.info(log_message)
        except Exception as ex:
            log_message = f"exception {ex}"
            if TERMINAL_LOGGING:
                print(datetime.datetime.now().strftime("%H:%M:%S"), log_message)
            logging.info(log_message)
            DWM.write("lec\r".encode())
            time.sleep(1)
            continue
    DWM.write("\r".encode())
    DWM.close()


if __name__ == "__main__":
    init()
