run: ./dev/pc.py ./src/main.py
	./dev/pc.py
	./build/main

build: ./dev/pc.py ./src/main.py
	./dev/pc.py

release: ./dev/pc.py ./src/main.py
	./dev/pc.py --enable-lto
