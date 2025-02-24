#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
import shutil
import yaml  # Требуется установить PyYAML (pip install pyyaml)
import logging

# Определение путей
HOME_DIR = os.path.expanduser("~")
ASSIST_DIR = os.path.join(HOME_DIR, ".assistme")
WORK_DIR = os.path.join(ASSIST_DIR, "session")
CONFIG_FILE = os.path.join(ASSIST_DIR, "config.yaml")
LOG_FILE = os.path.join(ASSIST_DIR, "log.txt")
WHISPER_DIR = os.path.join(ASSIST_DIR, "whisper.cpp")

# Создаем необходимые директории до настройки логирования
os.makedirs(ASSIST_DIR, exist_ok=True)
os.makedirs(WORK_DIR, exist_ok=True)

# Если лог-файл не существует, создаем его пустым
if not os.path.exists(LOG_FILE):
    open(LOG_FILE, 'a').close()

# Файлы записи и конвертации в поддиректории WORK_DIR
RECORD_FILE = os.path.join(WORK_DIR, "record.mp3")
OUTPUT_FILE = os.path.join(WORK_DIR, "output.wav")

# Значения по умолчанию для аудио-устройств
DEFAULT_CONFIG = {
    "audio_input_1": ":0",   # микрофон
    "audio_input_2": ":3"    # системный звук через BlackHole 16ch
}

# Настройка логирования: вывод в файл и консоль
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

file_handler = logging.FileHandler(LOG_FILE)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

def run_command(cmd, cwd=None):
    """Выполняет системную команду с логированием и проверкой ошибок."""
    logger.info(f"Выполнение: {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        logger.error(f"Ошибка выполнения команды: {cmd}")
        logger.error(f"Вывод stdout:\n{result.stdout}")
        logger.error(f"Вывод stderr:\n{result.stderr}")
        return False, result.stdout + result.stderr
    logger.info(f"Команда выполнена успешно: {cmd}")
    return True, result.stdout

def check_brew():
    """Проверяет наличие Homebrew в системе."""
    if shutil.which("brew") is None:
        logger.error("Homebrew не найден. Пожалуйста, установите Homebrew с https://brew.sh/")
        return False
    logger.info("Homebrew найден.")
    return True

def ensure_directory(path):
    """Создает указанную директорию, если она не существует."""
    if not os.path.isdir(path):
        os.makedirs(path)
        logger.info(f"Создана директория: {path}")

def ensure_assist_dir():
    """Создает директорию .assistme в домашней папке."""
    ensure_directory(ASSIST_DIR)

def ensure_work_dir():
    """Создает поддиректорию для временных файлов и результатов транскрибации."""
    ensure_directory(WORK_DIR)

def load_config():
    """Загружает конфигурацию из YAML-файла, создавая дефолтную при отсутствии."""
    if not os.path.exists(CONFIG_FILE):
        logger.info("Конфигурационный файл не найден, создаю дефолтный.")
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_FILE, "r") as f:
            config = yaml.safe_load(f)
            if not config:
                config = DEFAULT_CONFIG
    except Exception as e:
        logger.error(f"Ошибка чтения конфигурационного файла: {e}")
        config = DEFAULT_CONFIG
    return config

def save_config(config):
    """Сохраняет конфигурацию в YAML-файл."""
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f)
    logger.info(f"Конфигурация сохранена в {CONFIG_FILE}")

def install_command(args):
    """Команда install: установка Homebrew, ffmpeg, blackhole, клонирование и сборка whisper.cpp."""
    if not check_brew():
        sys.exit(1)
    
    for pkg in ["ffmpeg", "blackhole-16ch"]:
        logger.info(f"Устанавливаю {pkg} через brew...")
        success, _ = run_command(f"brew install {pkg}")
        if not success:
            logger.error(f"Ошибка установки {pkg}. Прерывание установки.")
            sys.exit(1)
    
    ensure_assist_dir()
    ensure_work_dir()

    if not os.path.isdir(WHISPER_DIR):
        logger.info("Клонирование репозитория whisper.cpp...")
        success, _ = run_command(f"git clone https://github.com/ggerganov/whisper.cpp.git {WHISPER_DIR}")
        if not success:
            logger.error("Ошибка клонирования whisper.cpp.")
            sys.exit(1)
    else:
        logger.info("Репозиторий whisper.cpp уже существует, пропускаю клонирование.")

    logger.info("Скачивание модели ggml-large-v2...")
    success, _ = run_command("sh ./models/download-ggml-model.sh large-v2", cwd=WHISPER_DIR)
    if not success:
        logger.error("Ошибка скачивания модели.")
        sys.exit(1)

    logger.info("Запуск сборки whisper.cpp (cmake)...")
    success, _ = run_command("cmake -B build", cwd=WHISPER_DIR)
    if not success:
        logger.error("Ошибка генерации сборочных файлов (cmake).")
        sys.exit(1)
    success, _ = run_command("cmake --build build --config Release", cwd=WHISPER_DIR)
    if not success:
        logger.error("Ошибка сборки whisper.cpp.")
        sys.exit(1)

    logger.info("Команда install выполнена успешно.")

def record_command(args):
    """Команда record: запись звука через ffmpeg с параметрами из конфигурации."""
    ensure_assist_dir()
    ensure_work_dir()
    config = load_config()

    audio_input_1 = config.get("audio_input_1", DEFAULT_CONFIG["audio_input_1"])
    audio_input_2 = config.get("audio_input_2", DEFAULT_CONFIG["audio_input_2"])

    ffmpeg_cmd = (f'ffmpeg -f avfoundation -i "{audio_input_1}" '
                  f'-f avfoundation -i "{audio_input_2}" '
                  f'-filter_complex amerge=inputs=2 "{RECORD_FILE}"')
    logger.info("Запуск записи звука. Для остановки записи используйте Ctrl+C.")
    try:
        subprocess.run(ffmpeg_cmd, shell=True, check=True)
    except KeyboardInterrupt:
        logger.info("Запись остановлена пользователем.")
    except subprocess.CalledProcessError as e:
        logger.error("Ошибка записи звука:")
        logger.error(e)
        sys.exit(1)

def transcribate_command(args):
    """Команда transcribate: конвертация аудиофайла, транскрибация и сохранение результатов в WORK_DIR."""
    ensure_assist_dir()
    ensure_work_dir()
    
    if not os.path.exists(RECORD_FILE):
        logger.error(f"Файл записи {RECORD_FILE} не найден. Сначала выполните команду record.")
        sys.exit(1)
    
    ffmpeg_conv_cmd = (f'ffmpeg -i "{RECORD_FILE}" -af "lowpass=f=4000" '
                       f'-ar 16000 -ac 1 -c:a pcm_s16le "{OUTPUT_FILE}"')
    logger.info("Конвертация аудиофайла...")
    success, _ = run_command(ffmpeg_conv_cmd)
    if not success:
        logger.error("Ошибка конвертации файла.")
        sys.exit(1)

    whisper_cli = os.path.join(WHISPER_DIR, "build", "bin", "whisper-cli")
    model_path = os.path.join(WHISPER_DIR, "models", "ggml-large-v2.bin")
    if not os.path.exists(whisper_cli):
        logger.error("Бинарный файл whisper-cli не найден. Проверьте, что команда install выполнена успешно.")
        sys.exit(1)
    
    transcribe_cmd = (f'"{whisper_cli}" -t 8 -p 2 -m "{model_path}" '
                      f'-l ru --output-txt -f "{OUTPUT_FILE}"')
    logger.info("Запуск транскрибации...")
    success, output = run_command(transcribe_cmd, cwd=WORK_DIR)
    if not success:
        logger.error("Ошибка транскрибации.")
        sys.exit(1)
    else:
        logger.info("Транскрибация завершена успешно. Результат:")
        logger.info(output)
        print(output)

    logger.info(f"Временные файлы сохранены в {WORK_DIR}")

def main():
    parser = argparse.ArgumentParser(description="Assistme: CLI инструмент для настройки транскрибации на macOS")
    subparsers = parser.add_subparsers(dest="command", help="Доступные команды")

    parser_install = subparsers.add_parser("install", help="Установка зависимостей")
    parser_install.set_defaults(func=install_command)

    parser_record = subparsers.add_parser("record", help="Запись звука")
    parser_record.set_defaults(func=record_command)

    parser_transcribate = subparsers.add_parser("transcribate", help="Выполнение транскрибации")
    parser_transcribate.set_defaults(func=transcribate_command)

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)
    else:
        args.func(args)

if __name__ == "__main__":
    main()
