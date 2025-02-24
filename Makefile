help:
	./cli.py -h

build:
	pyinstaller --onedir --log-level=WARN --nowindow cli.py

clean:
	rm -rf ./dist ./build cli.spec