import socket
import ssl
from selectors import KqueueSelector, EVENT_WRITE, EVENT_READ
from pyquery import PyQuery as pq

# coroutines in the standard "asyncio" library in Python 3.4 are built upon
# generators, a Future class, and the "yield from" statement

# features:
# there is no thread, only generator (naive coroutine)
# callbacks are totally eliminated

selector = KqueueSelector()

stoppable = False

urls_todo = set(['/'])
seen_urls = set(['/'])


class Future:
    def __init__(self):
        self.result = None
        self._callbacks = []

    def add_done_callback(self, fn):
        self._callbacks.append(fn)

    def set_result(self, result):
        # problem: merely setting the result of Future in generator doesn't cause the generator to resume
        # solution: use Task to trigger a send() to the generator when the Future is set
        # solution: this can be done in the callback of the Future
        self.result = result
        for fn in self._callbacks:
            fn()

    def clear_callback(self):
        self._callbacks = []


class Task:
    def __init__(self, coro):
        self.coro = coro
        self.step()

    def step(self):
        try:
            next_future = self.coro.send(None)
        except CancelledError:
            self.cancelled = True
            return
        except StopIteration:
            return

        next_future.clear_callback()
        next_future.add_done_callback(self.step)

    def cancel(self):
        self.coro.throw(CancelledError)


class Fetcher:
    def __init__(self, url):
        self.response = b''
        self.url = url
        self.sock = None

    def fetch(self):
        self.sock = socket.socket(socket.AF_INET)
        self.sock.setblocking(False)
        try:
            self.sock.connect(('dilbert.com', 80))
        except BlockingIOError:
            pass

        def connected():
            f.set_result(None)

        f = Future()

        selector.register(self.sock.fileno(), EVENT_WRITE, connected)

        yield f  # yield so caller can set the result of f

        # the content of the first callback can be put here
        selector.unregister(self.sock.fileno())
        request = 'GET {} HTTP/1.1\r\nHost: dilbert.com\r\nConnection: close\r\n\r\n'.format(
            self.url)
        self.sock.send(request.encode('ascii'))

        f2 = Future()

        def readable():
            f2.set_result(None)

        # unlike connected, the socket remains readable for some period of time
        selector.register(self.sock.fileno(), EVENT_READ, readable)

        yield f2  # yield so caller can set the result of f2

        # the content of the second callback can be put here
        global stoppable

        while True:
            yield f2
            chunk = self.sock.recv(4096)
            if chunk:
                self.response += chunk
            else:
                selector.unregister(self.sock.fileno())
                links = self.parse_link()

                for link in links.difference(seen_urls):
                    urls_todo.add(link)
                    Task(Fetcher(link).fetch())

                seen_urls.update(links)
                urls_todo.remove(self.url)
                # if there is nothing left to do
                if not urls_todo:
                    stoppable = True

    def parse_link(self):
        links = set([])
        d = pq(self.response)
        anchors = d("a")
        for anchor in anchors:
            href = anchor.get("href")
            if href and href[:5] == "http:" and href[7:14] == "dilbert":
                links.add(href[6:])
        return links


fetcher = Fetcher('/')
Task(fetcher.fetch())

while not stoppable:
    events = selector.select()
    for event_key, event_mask in events:
        callback = event_key.data
        callback()

print("processes " + str(len(seen_urls)) + " urls")
