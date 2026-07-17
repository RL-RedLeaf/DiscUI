from events import *

class EventMonitor:
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.event_bus.subscribe(Event, self.on_event)

    def on_event(self, event):
        print(f"EventMonitor: Received event: {event}")