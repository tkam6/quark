run: ./dev/pc.py ./src/main.py
	./dev/pc.py

build: ./dev/pc.py ./src/main.py
	./dev/pc.py

release: ./dev/pc.py ./src/main.py
	./dev/pc.py --enable-lto

debug: ./dev/pc.py ./src/main.py
	./dev/pc.py --debug-build
