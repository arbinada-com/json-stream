# json-sax-py

Stream JSON parser (SAX parser)

## About

SAX (Simple API for XML) is an event-driven online algorithm for lexing and parsing XML documents [(wiki)](https://en.wikipedia.org/wiki/Simple_API_for_XML).
Same kind of algorithm works also for JSON documents.

This is pure Python implementation, so if you are looking for a high performance parser, it is not the right choice.
Take a look at the C, C++, Rust and even C# which have highly optimizing compilers, or to third-party packages based on C/C++ modules.

## Why SAX parser?

- extremely low memory consuming: only the small JSON piece being parsed is loaded in the memory every time
- no third-party package dependencies: you just need to copy the `json_sax.py` module into your application
- can parse an infinite stream

These features may be valuable for embedded development, and for prototyping

## Examples

See in the `examples` folder

- `captor_data`: analyzing a time series stored as an array of objects. 
  When processing, only one object is loaded in the memory
