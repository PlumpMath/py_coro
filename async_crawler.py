from pyquery import PyQuery as pq
import asyncio
import socket

try:
    from asyncio import JoinableQueue as Queue
except ImportError:
    from asyncio import Queue

loop = asyncio.get_event_loop()

# this one is pretty much just minor modifications to coroutine_crawler:
# 1. change the asyncio.coroutine decorator to `async def` declaration
# 2. replace `yield from` with await


class Fetcher:
    def __init__(self, loop):
        self.num_worker = 10
        self.loop = loop
        self.q = Queue()
        self.seen_urls = set(['/'])

    async def manager(self):
        workers = [self.loop.create_task(self.worker())
                   for _ in range(self.num_worker)]
        # the `yield from` is not needed
        await self.q.put('/')
        # wait until q is empty
        await self.q.join()
        for w in workers:
            w.cancel()

    async def worker(self):
        while True:
            url = await self.q.get()

            sock = socket.socket(socket.AF_INET)
            sock.setblocking(False)
            try:
                await self.loop.sock_connect(sock, ('dilbert.com', 80))
            except BlockingIOError:
                pass

            request = 'GET {} HTTP/1.1\r\nHost: dilbert.com\r\nConnection: close\r\n\r\n'.format(
                url)
            await self.loop.sock_sendall(sock, request.encode('ascii'))

            response = b''
            chunk = await self.loop.sock_recv(sock, 4096)
            while chunk:
                response += chunk
                chunk = await self.loop.sock_recv(sock, 4096)

            links = await self.parse_link(response)
            for link in links.difference(self.seen_urls):
                await self.q.put(link)

            self.seen_urls.update(links)
            self.q.task_done()
            sock.close()

    async def parse_link(self, response):
        links = set([])
        d = pq(response)
        anchors = d("a")
        for anchor in anchors:
            href = anchor.get("href")
            if href and href[:5] == "http:" and href[7:14] == "dilbert":
                links.add(href[6:])
        return links


fetcher = Fetcher(loop)
loop.run_until_complete(fetcher.manager())
loop.close()

print("processes " + str(len(fetcher.seen_urls)) + " urls")
