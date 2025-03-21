- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
   * [Basic Commands](#basic-commands)
   * [Global Options](#global-options)
- [Configuration](#configuration)
- [Internationalization](#internationalization)
- [License](#license)
- [Contributing](#contributing)

# Assist Me: CLI Audio Transcription Tool for macOS

Assist Me is a command-line tool that automates the process of recording and transcribing audio on macOS. It handles dependency installation, audio recording, transcription using [whisper.cpp](https://github.com/ggerganov/whisper.cpp), and configuration management—all with built-in internationalization (i18n) support.

## Features

- **Installation:** Installs required packages (ffmpeg, blackhole, etc.) via Homebrew and builds the whisper.cpp project.
- **Recording:** Captures audio using ffmpeg with configurable audio input/output devices.
- **Transcription:** Converts and transcribes recordings using whisper.cpp.
- **Stream Mode:** Optionally perform transcription immediately after recording.
- **Settings Management:** Update and retrieve configuration settings using `env set` and `env get` commands.
- **Internationalization:** Supports English and Russian, with translations loaded from a JSON file.
- **Custom Configuration:** Specify a custom configuration file path via the `-c/--config` flag.

## Requirements

- macOS
- Python 3.x
- Homebrew (for installing dependencies)
- Git
- ffmpeg (installed via Homebrew)
- PyYAML (`pip install pyyaml`)

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/your-username/assistme-cli.git
   ```

2. Change to the project directory:

   ```bash
   cd assistme-cli
   ```

3. (Optional) Set up a virtual environment and install dependencies:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   poetry install
   ```

4. Ensure Homebrew is installed on your system.

## Usage

### Basic Commands

- **Install Dependencies and Build whisper.cpp:**

  ```bash
  ./assistme.py env install
  ```

- **Record Audio:**

  ```bash
  ./assistme.py record
  ```
  
  Aliases: `r` or `rec`

- **Transcribe Audio:**

  ```bash
  ./assistme.py transcribate
  ```
  
  Aliases: `t` or `trb`

- **Combined Record and Transcribe (Stream Mode):**

  ```bash
  ./assistme.py record --stream
  ```

- **Update Configuration Settings:**

  ```bash
  ./assistme.py env set audio.input=:0 audio.output=:3 lang=ru
  ```

- **Retrieve a Configuration Setting:**

  ```bash
  ./assistme.py env get audio.input
  ```

### Global Options

- **Language Selection:**

  Override the interface language with the `-l` flag:

  ```bash
  ./assistme.py -l en record
  ```

- **Custom Configuration File:**

  Specify a custom configuration file using the `-c/--config` flag:

  ```bash
  ./assistme.py -c /path/to/myconfig.yaml record
  ```

## Configuration

The default configuration file is stored at `~/.assistme/config.yaml` and is created automatically on first run. It includes settings such as:

- **Language:** `lang` (default: "en")
- **Audio Devices:** `audio.input` (default: ":0") and `audio.output` (default: ":3")
- **Other Options:** e.g. `keep_source`, `stream_mode`

## Internationalization

All user-facing messages are localized. Translations are stored in `translations.json` (located in the same directory as the script) and currently support English (`en`) and Russian (`ru`). You can set the language via the `-l/--language` flag or by updating the configuration file.

## License

This project is licensed under the MIT License.

## Contributing

Contributions, bug reports, and feature requests are welcome. Please open an issue or submit a pull request on [GitHub](https://github.com/your-username/assistme-cli).