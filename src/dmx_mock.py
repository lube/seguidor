import logging
import datetime

TERMINAL_LOGGING = False


def log(line):
    if TERMINAL_LOGGING:
        print(datetime.datetime.now().strftime("%H:%M:%S"), line)
    logging.info(line)


class MockDMXInterface:
    def __init__(self):
        log("Mock DMX interface initialized")

    def set_channel(self, channel, value):
        log(f"Sending value {value} to channel {channel}")

    def blackout(self):
        print("blackout")

    def render(self):
        print("render")
