import socket
import ssl
from selectors import KqueueSelector, EVENT_WRITE, EVENT_READ
from pyquery import PyQuery as pq

# spaghetti code
# without threads, a series of operations cannot be collected into a single function
# stack trace is broken: stack ripping

selector = KqueueSelector()

stoppable = False

urls_todo = set(['/'])
seen_urls = set(['/'])


class Fetcher:
    def __init__(self, url):
        self.response = b''
        self.url = url
        self.sock = None

    # first callback
    def connected(self, key, mask):
        selector.unregister(key.fd)
        request = 'GET {} HTTP/1.1\r\nHost: dilbert.com\r\nConnection: close\r\n\r\n'.format(
            self.url)
        self.sock.send(request.encode('ascii'))
        selector.register(self.sock.fileno(), EVENT_READ, self.readable)

    # second callback
    def readable(self, key, mask):
        global stoppable
        chunk = self.sock.recv(4096)
        if chunk:
            self.response += chunk
        else:
            selector.unregister(key.fd)
            links = self.parse_link()

            for link in links.difference(seen_urls):
                urls_todo.add(link)
                Fetcher(link).fetch()

            seen_urls.update(links)
            urls_todo.remove(self.url)
            # if there is nothing left to do
            if not urls_todo:
                stoppable = True

    def fetch(self):
        self.sock = socket.socket(socket.AF_INET)
        self.sock.setblocking(False)
        try:
            self.sock.connect(('dilbert.com', 80))
        except BlockingIOError:
            pass

        selector.register(self.sock.fileno(), EVENT_WRITE, self.connected)

    def parse_link(self):
        links = set([])
        d = pq(self.response)
        anchors = d("a")
        for anchor in anchors:
            href = anchor.get("href")
            if href[:5] == "http:" and href[7:14] == "dilbert":
                links.add(href[6:])
        return links


fetcher = Fetcher('/')
fetcher.fetch()

while not stoppable:
    events = selector.select()
    for event_key, event_mask in events:
        callback = event_key.data
        callback(event_key, event_mask)

print("processes " + str(len(seen_urls)) + " urls")
