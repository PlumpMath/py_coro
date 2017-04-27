from selectors import KqueueSelector, EVENT_WRITE, EVENT_READ
from pyquery import PyQuery as pq
import asyncio
import socket

try:
	from asyncio import JoinableQueue as Queue
except ImportError:
	from asyncio import Queue

loop = asyncio.get_event_loop()


class Fetcher:
	def __init__(self, loop):
		self.num_worker = 10
		self.loop = loop
		self.q = Queue()
		self.seen_urls = set(['/'])

	@asyncio.coroutine
	def manager(self):
		workers = [self.loop.create_task(self.worker()) for _ in range(self.num_worker)]
		# the `yield from` is not be needed because it only blocks when q is full
		yield from self.q.put('/')
		# wait until q is empty
		yield from self.q.join()
		for w in workers:
			w.cancel()


	@asyncio.coroutine
	def worker(self):
		while True:
			url = yield from self.q.get()
			# print("get " + url)

			sock = socket.socket(socket.AF_INET)
			sock.setblocking(False)
			try:
				# self.sock.connect(('dilbert.com', 80))
				yield from self.loop.sock_connect(sock, ('dilbert.com', 80))
			except BlockingIOError:
				pass

			request = 'GET {} HTTP/1.1\r\nHost: dilbert.com\r\nConnection: close\r\n\r\n'.format(url)
			yield from self.loop.sock_sendall(sock, request.encode('ascii'))

			response = b''
			chunk = yield from self.loop.sock_recv(sock, 4096)
			while chunk:
				response += chunk
				chunk = yield from self.loop.sock_recv(sock, 4096)

			links = yield from self.parse_link(response)
			for link in links.difference(self.seen_urls):
				# print(link)
				yield from self.q.put(link)

			self.seen_urls.update(links)
			self.q.task_done()
			sock.close()


	@asyncio.coroutine
	def parse_link(self, response):
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
