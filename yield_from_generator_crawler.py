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

    def __iter__(self):
        # can now use `yield from` everywhere
        # Tell Task to resume me here.
        yield self
        return self.result


# coroutine driver
# can actually replaced by a python decorator
class Task:
    def __init__(self, coro):
        self.coro = coro
        self.step()

    def step(self):
        try:
            next_future = self.coro.send(None)
        except StopIteration:
            return

        next_future.clear_callback()
        next_future.add_done_callback(self.step)


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

        yield from f  # yield so caller can set the result of f

        # the content of the first callback can be put here
        selector.unregister(self.sock.fileno())
        request = 'GET {} HTTP/1.1\r\nHost: dilbert.com\r\nConnection: close\r\n\r\n'.format(
            self.url)
        self.sock.send(request.encode('ascii'))

        # delegate to another generator
        yield from self.recv_data()

    # just like normal sub-routine, instead it is implemented as a coroutine
    # the yield from statement is a frictionless channel,
    # through which values flow in and out of recv_data without affecting fetch
    # until gen completes.
    def recv_data(self):
        global stoppable

        f2 = Future()

        def readable():
            f2.set_result(None)

        selector.register(self.sock.fileno(), EVENT_READ, readable)

        while True:
            yield from f2

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
