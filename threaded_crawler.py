from queue import Queue
import socket
from threading import Thread
from pyquery import PyQuery as pq

# a thread pool of 10 workers
# each contends for url from a queue


seen_urls = set(['/'])
urls_todo = Queue()
urls_todo.put('/')

# thread function
def worker():
	global urls_todo
	global seen_urls

	while True:
		url = urls_todo.get()
		if url == "34567":
			urls_todo.task_done()
			break

		sock = socket.socket(socket.AF_INET)
		sock.setblocking(True)
		sock.connect(('dilbert.com', 80))
		request = 'GET {} HTTP/1.1\r\nHost: dilbert.com\r\nConnection: close\r\n\r\n'.format(
			url)
		sock.send(request.encode('ascii'))
		chunk = sock.recv(4096)
		response = b''
		
		while chunk:
			response += chunk
			chunk = sock.recv(4096)
		
		sock.close()
		links = parse_link(response)
		different_links = links.difference(seen_urls)

		urls_todo.task_done()

		for link in different_links:
			urls_todo.put_nowait(link)
			# don't care about its result
		seen_urls.update(links)


def parse_link(response):
	links = set([])
	d = pq(response)
	anchors = d("a")
	for anchor in anchors:
		href = anchor.get("href")
		if href and href[:5] == "http:" and href[7:14] == "dilbert":
			links.add(href[6:])
	return links


for _ in range(1,4):
	t = Thread(target=worker)
	t.start()


urls_todo.join()
for _ in range(1,4):
	urls_todo.put("34567")
urls_todo.join()

print("processes " + str(len(seen_urls)) + " urls")
