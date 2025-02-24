clean:
	rm -rf ./dist ./build cli.spec

build:
	pyinstaller --onefile --nowindow --log-level=WARN --add-data="translations.json:." --optimize 2 cli.py