import asyncio
import aiohttp
from pyquery import PyQuery as pq

# `yield from` semantics
# 1. wait for a Future to be ready
# 2. `invoke` another coroutine


try:
	from asyncio import JoinableQueue as Queue
except ImportError:
	from asyncio import Queue


class Crawler:
	def __init__(self, root_url, max_redirect, loop):
		self.max_tasks = 10
		self.max_redirect = max_redirect
		self.q = Queue()
		self.seen_urls = set()
		self.loop = loop

		self.session = aiohttp.ClientSession(loop=self.loop)

		self.q.put_nowait((root_url, self.max_redirect))

	@asyncio.coroutine
	def crawl(self):
		"""Run the crawler until all work is done."""
		workers = [self.loop.create_task(self.work()) 
				   for _ in range(self.max_tasks)]

		# When all work is done, exit
		yield from self.q.join()
		for w in workers:
			w.cancel()
		self.session.close()

	@asyncio.coroutine
	def work(self):
		while True:
			url, max_redirect = yield from self.q.get()
			print("working on " + url + " with " + str(max_redirect) + " max_redirect")

			# Download page and add new links to self.q.
			yield from self.fetch(url, max_redirect)
			self.q.task_done()

	@asyncio.coroutine
	def fetch(self, url, max_redirect):
		response = yield from self.session.get(
			url, allow_redirects=False)

		try:
			if self.is_redirect(response):
				if max_redirect > 0:
					next_url = response.headers['location']
					if next_url in self.seen_urls:
						# We have been down this path before.
						return

					# Remember we have seen this URL.
					self.seen_urls.add(next_url)

					# Follow the redirect. One less redirect remains.
					self.q.put_nowait((next_url, max_redirect - 1))
			else:
				links = yield from self.parse_links(response)
				for link in links.difference(self.seen_urls):
					print("adding " + link + ", now the number of urls in the queue is " + str(self.q.qsize()))
					self.q.put_nowait((link, self.max_redirect))
				self.seen_urls.update(links)
		finally:
			pass


	def is_redirect(self, response):
		return response.status in (300, 301, 302, 303, 307)

	
	@asyncio.coroutine
	def parse_links(self, response):
		# response is a coroutine
		links = set([])
		html = yield from response.read()
		d = pq(html)
		anchors = d("a")
		for anchor in anchors:
			href = anchor.get("href")
			if href and href[:5] == "http:" and href[7:14] == "dilbert":
				links.add(href)
		return links

loop = asyncio.get_event_loop()
crawler = Crawler('http://dilbert.com',
						   max_redirect=10, loop=loop)
loop.run_until_complete(crawler.crawl())
loop.close()
print("Crawling complete!")
