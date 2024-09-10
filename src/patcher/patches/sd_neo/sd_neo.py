import StreamDeck
import StreamDeck.Devices

from .StreamDeckNeo import StreamDeckNeo

StreamDeck.Devices.StreamDeckNeo = StreamDeckNeo

# Device Manager
from StreamDeck import DeviceManager
DeviceManager.USB_PID_STREAMDECK_NEO = 0x009a