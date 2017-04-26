import socket
from selectors import KqueueSelector, EVENT_WRITE

# scenario: applications with many slow or sleepy connections with infrequent events

selector = KqueueSelector()

sock = socket.socket()
sock.setblocking(False)
try:
    sock.connect(('xkcd.com', 80))
except BlockingIOError:
    pass


def connected():
    selector.unregister(sock.fileno())
    print('connected!')

# register for when the socket is writable
selector.register(sock.fileno(), EVENT_WRITE, connected)

def loop():
	while True:
		events = selector.select()
		for event_key, event_mask in events:
			# the callback function is stored in event_key.data
			callback = event_key.data
			callback()

loop()
