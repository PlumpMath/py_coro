# py_coro

This repo aims at providing a POC of progressive implementation of python coroutine. All implementations aim at realising a crawler for dilbert.com.

You can follow the below roadmap to see how python coroutine reaches where it is today:

threaded -> callback -> generator -> `yield from` generator -> coroutine -> async

for implementations after callback, I trace from the `async def` and `await` syntax introduced in PEP 492 all the way back to the generator primitives.

The mechanism of python generator is heap frame which has its own stack. For possible C impl (Python impl can also be seen in its source code), check [libtask](https://github.com/jamwt/libtask)