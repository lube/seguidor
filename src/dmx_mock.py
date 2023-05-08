TERMINAL_LOGGING = True


class MockDMXInterface:
    def __init__(self):
        if TERMINAL_LOGGING:
            print("Mock DMX interface initialized")

    def set_channel(self, channel, value):
        if TERMINAL_LOGGING:
            print(f"Sending value {value} to channel {channel}")

    def blackout(self):
        if TERMINAL_LOGGING:
            print("blackout")

    def render(self):
        if TERMINAL_LOGGING:
            print("render")
