import json
import tkinter as tk
from tkinter import ttk
import math
import geometry_utils as g

SCALING_CANVAS = 50
OFFSET_CANVAS_X = 50
OFFSET_CANVAS_Y = 50

WIDTH_EXT = 700
WIDTH_INN = 650
HEIGHT_EXT = 250
HEIGHT_INN = 250

colors = ["blue", "green", "orange", "red"]


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

    def save_anchor_colors(self):
        with open("./anchor_colors.json", "w") as outfile:
            json.dump(self.anchor_colors, outfile)

    def save_ui_configs(self):
        with open("./ui.json", "w") as outfile:
            json.dump([self.offset_x, self.offset_y, self.scale, self.rotation_angle], outfile)

    def load_anchor_colors(self):
        try:
            with open("./anchor_colors.json", "r") as infile:
                self.anchor_colors = json.load(infile)
        except FileNotFoundError:
            print(f"No previous anchor colors found. Using default colors.")

    def load_ui_configs(self):
        try:
            with open("./ui.json", "r") as infile:
                [self.offset_x, self.offset_y, self.scale, self.rotation_angle] = json.load(infile)
        except FileNotFoundError:
            print(f"No previous ui found. Using default params.")

    def toggle_anchor_color(self, anchor_index):
        self.anchor_colors[anchor_index] = (self.anchor_colors[anchor_index] + 1) % 4
        self.save_anchor_colors()

    def on_anchor_click(self, event, anchor_index):
        self.toggle_anchor_color(anchor_index)

    def update_position(self, pos):
        self.x_filtered = pos[0]
        self.y_filtered = pos[1]
        self.z_filtered = pos[2]

    def update_anchor_positions(self, anchor_positions):
        self.anchor_positions = anchor_positions
        self.anchor_colors = [0] * len(self.anchor_positions)

    def rotate_scale_and_offset(self, center, pos, canvas):
        x_rot, y_rot = g.rotate((pos[0], pos[1]), (0, 0), self.rotation_angle)
        x = (x_rot * self.scale + canvas.winfo_width() / 2) - self.offset_x
        y = (y_rot * self.scale + canvas.winfo_height() / 2) - self.offset_y
        (x, y) = g.flip_x((x, y), center)
        return x, y

    def init_visualizer(self):
        def on_closing():
            root.destroy()

        root = tk.Tk()
        root.protocol("WM_DELETE_WINDOW", on_closing)
        root.title("UWB Position Visualizer")
        tabControl = ttk.Notebook(root)

        tab1 = tk.Frame(tabControl)
        tab2 = tk.Frame(tabControl)
        tab1.grid(column=4, row=1)
        tab2.grid(column=3, row=4)

        label1 = tk.Label(tab2, text="Set tilt/pan on pos 1")
        label1.grid(row=0, column=0)

        int_input1 = tk.Entry(tab2, width=5)
        int_input1.grid(row=0, column=1, padx=5)
        int_input2 = tk.Entry(tab2, width=5)
        int_input2.grid(row=0, column=2, padx=5)

        pos1, pos2 = [], []
        pos1tilt, pos1pan = 0, 1
        pos2tilt, pos2pan = 0, 1

        def save_pos_1():
            nonlocal pos1, pos1tilt, pos1pan
            pos1 = [self.x_filtered, self.y_filtered, self.z_filtered]
            pos1tilt = int(int_input1.get())
            pos1pan = int(int_input2.get())

        button1 = tk.Button(tab2, text="Save Pos 1", command=save_pos_1)
        button1.grid(row=0, column=3, padx=20)

        label2 = tk.Label(tab2, text="Set tilt/pan on pos 2")
        label2.grid(row=1, column=0, padx=20)

        int_input3 = tk.Entry(tab2, width=5)
        int_input3.grid(row=1, column=1, padx=5)
        int_input4 = tk.Entry(tab2, width=5)
        int_input4.grid(row=1, column=2, padx=5)

        def save_pos_2():
            nonlocal pos2, pos2tilt, pos2pan
            pos2 = [self.x_filtered, self.y_filtered, self.z_filtered]
            pos2tilt = int(int_input3.get())
            pos2pan = int(int_input4.get())

        button2 = tk.Button(tab2, text="Save Pos 2", command=save_pos_2)
        button2.grid(row=1, column=3, padx=20)

        def calibrate_system():
            nonlocal pos1, pos1tilt, pos1pan, pos2, pos2tilt, pos2pan, label3
            dmx_values = [(pos1tilt, pos1pan), (pos2tilt, pos2pan)]
            tag_positions = [pos1, pos2]

            dmx_pans, dmx_tilts = zip(*dmx_values)
            tag_xs, tag_ys, _ = zip(*tag_positions)

            sum_x = sum(tag_xs)
            sum_y = sum(tag_ys)
            sum_pan = sum(dmx_pans)
            sum_tilt = sum(dmx_tilts)

            n = len(tag_xs)

            pan_offset = (sum_pan - sum_x) / n
            tilt_offset = (sum_tilt - sum_y) / n

            pan_scale = sum([(dmx_pans[i] - pan_offset) / tag_xs[i] for i in range(n)]) / n
            tilt_scale = sum([(dmx_tilts[i] - tilt_offset) / tag_ys[i] for i in range(n)]) / n

            label3.config(text=f"Pan offset: {pan_offset:.2f}, Tilt offset: {tilt_offset:.2f}, Pan scale: {pan_scale:.2f}, Tilt scale: {tilt_scale:.2f}")

        button3 = tk.Button(tab2, text="Calculate offsets and scales", command=calibrate_system)
        button3.grid(row=2, column=0, padx=20)

        label3 = tk.Label(tab2, text="xxx")
        label3.grid(row=2, column=3, padx=20)

        frame = tk.Frame(root, width=WIDTH_EXT, height=HEIGHT_EXT)
        frame.pack_propagate(False)  # Prevent the frame to resize to its content
        frame.pack()

        canvas = tk.Canvas(frame, width=WIDTH_INN, height=HEIGHT_INN, bg="white")
        canvas.pack()

        position_label = tk.Label(root, text="Position: (0.00, 0.00, 0.00)", font=("Arial", 13), pady=10)
        position_label.pack()

        self.load_ui_configs()

        def rotate_ccw():
            self.rotation_angle += math.radians(2)
            self.save_ui_configs()

        def rotate_cw():
            self.rotation_angle += math.radians(-2)
            self.save_ui_configs()

        offset_x_slider = tk.Scale(tab1, from_=-200, to=200, resolution=20, orient="horizontal",
                                   label="Offset X",
                                   length=200)
        offset_x_slider.set(self.offset_x)  # Set the initial value to the current offset
        offset_x_slider.grid(row=0, column=0, padx=20, pady=20)  # Changed to grid()

        offset_y_slider = tk.Scale(tab1, from_=-100, to=100, resolution=20, orient="horizontal",
                                   label="Offset Y",
                                   length=200)
        offset_y_slider.set(self.offset_y)  # Set the initial value to the current offset
        offset_y_slider.grid(row=0, column=1, padx=20, pady=20)  # Changed to grid()

        scale_slider = tk.Scale(tab1, from_=10, to=200, resolution=10, orient="horizontal", label="Scaling",
                                length=200)
        scale_slider.set(self.scale)  # Set the initial value to the current scaling
        scale_slider.grid(row=0, column=2, padx=20, pady=20)  # Changed to grid()

        rot_frame = tk.Frame(tab1)
        rot_frame.columnconfigure(1)
        rot_frame.grid(row=0, column=3, padx=20, pady=20)

        button_ccw = tk.Button(rot_frame, text="Rotate CCW", command=rotate_ccw)
        button_ccw.pack()
        button_cw = tk.Button(rot_frame, text="Rotate CW", command=rotate_cw)
        button_cw.pack()

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
                self.save_ui_configs()

            x, y = self.rotate_scale_and_offset(center, (self.x_filtered, self.y_filtered), canvas)

            canvas.delete("all")
            canvas.create_oval(x - self.dot_radius, y - self.dot_radius, x + self.dot_radius, y + self.dot_radius,
                               fill="purple")

            for index, (x, y, z) in enumerate(self.anchor_positions):
                x, y = self.rotate_scale_and_offset(center, (x, y), canvas)

                anchor = canvas.create_oval(x - self.dot_radius, y - self.dot_radius,
                                            x + self.dot_radius, y + self.dot_radius,
                                            fill=colors[self.anchor_colors[index]])
                canvas.tag_bind(anchor, "<Button-1>",
                                lambda event, anchor_index=index: self.on_anchor_click(event,
                                                                                       anchor_index=anchor_index))

            position_label.config(
                text=f"Position: ({self.x_filtered:.2f}, {self.y_filtered:.2f}, {self.z_filtered:.2f})")
            root.after(100, update)

        tabControl.add(tab1, text='Setup view')
        tabControl.add(tab2, text='Setup light')
        tabControl.pack(expand=1, fill="both")

        update()
        root.mainloop()
