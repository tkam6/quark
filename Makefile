run: ./dev/pc.py ./src/main.py
	./dev/pc.py -r

build: ./dev/pc.py ./src/main.py
	./dev/pc.py

release: ./dev/pc.py ./src/main.py
	./dev/pc.py -e release

debug: ./dev/pc.py ./src/main.py
	./dev/pc.py -e debug
