clean:
	rm -rf ./dist ./build assistme.spec

build:
	pyinstaller --onefile --nowindow --log-level=WARN --add-data="translations.json:." --name=assistme --optimize 2 assistme.py