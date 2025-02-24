#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
import shutil
import yaml  # Требуется установить PyYAML (pip install pyyaml)
import logging
import re

# Определение путей
HOME_DIR = os.path.expanduser("~")
ASME_DIR = os.path.join(HOME_DIR, ".assistme")
ASME_WORK_DIR = os.path.join(ASME_DIR, "session")
ASME_CONFIG_FILE = os.path.join(ASME_DIR, "config.yaml")
ASME_LOG_FILE = os.path.join(ASME_DIR, "log.txt")
ASME_WHISPER_DIR = os.path.join(ASME_DIR, "whisper.cpp")

# Файлы записи и конвертации в поддиректории WORK_DIR
ASME_RECORD_FILE = os.path.join(ASME_WORK_DIR, "record.mp3")
ASME_OUTPUT_FILE = os.path.join(ASME_WORK_DIR, "output.wav")

# Значения по умолчанию для аудио-устройств
DEFAULT_CONFIG = {
    "audio_input_1": ":0",   # микрофон
    "audio_input_2": ":3"    # системный звук через BlackHole 16ch
}

# Создаем необходимые директории до настройки логирования
os.makedirs(ASME_DIR, exist_ok=True)
os.makedirs(ASME_WORK_DIR, exist_ok=True)

# Если лог-файл не существует, создаем его пустым
if not os.path.exists(ASME_LOG_FILE):
    open(ASME_LOG_FILE, 'a').close()

# Настройка логирования: вывод в файл и консоль
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

file_handler = logging.FileHandler(ASME_LOG_FILE)
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
    ensure_directory(ASME_DIR)

def ensure_work_dir():
    """Создает поддиректорию для временных файлов и результатов транскрибации."""
    ensure_directory(ASME_WORK_DIR)

def load_config():
    """Загружает конфигурацию из YAML-файла, создавая дефолтную при отсутствии."""
    if not os.path.exists(ASME_CONFIG_FILE):
        logger.info("Конфигурационный файл не найден, создаю дефолтный.")
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    try:
        with open(ASME_CONFIG_FILE, "r") as f:
            config = yaml.safe_load(f)
            if not config:
                config = DEFAULT_CONFIG
    except Exception as e:
        logger.error(f"Ошибка чтения конфигурационного файла: {e}")
        config = DEFAULT_CONFIG
    return config

def save_config(config):
    """Сохраняет конфигурацию в YAML-файл."""
    with open(ASME_CONFIG_FILE, "w") as f:
        yaml.dump(config, f)
    logger.info(f"Конфигурация сохранена в {ASME_CONFIG_FILE}")

def install_command(args):
    """Команда install: установка Homebrew, ffmpeg, blackhole, клонирование и сборка whisper.cpp.
    Добавлена оптимизация: если репозиторий уже скачан и собран, то сборка повторно не выполняется."""
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

    # Проверка, что репозиторий whisper.cpp уже скачан
    if not os.path.isdir(ASME_WHISPER_DIR):
        logger.info("Клонирование репозитория whisper.cpp...")
        success, _ = run_command(f"git clone https://github.com/ggerganov/whisper.cpp.git {ASME_WHISPER_DIR}")
        if not success:
            logger.error("Ошибка клонирования whisper.cpp.")
            sys.exit(1)
    else:
        logger.info("Репозиторий whisper.cpp уже существует, пропускаю клонирование.")

    # Проверка, скачана ли модель ggml-large-v2
    model_file = os.path.join(ASME_WHISPER_DIR, "models", "ggml-large-v2.bin")
    if not os.path.exists(model_file):
        logger.info("Скачивание модели ggml-large-v2...")
        success, _ = run_command("sh ./models/download-ggml-model.sh large-v2", cwd=ASME_WHISPER_DIR)
        if not success:
            logger.error("Ошибка скачивания модели.")
            sys.exit(1)
    else:
        logger.info("Модель ggml-large-v2 уже скачана, пропускаю загрузку модели.")

    # Проверка, собран ли бинарник whisper-cli
    whisper_cli = os.path.join(ASME_WHISPER_DIR, "build", "bin", "whisper-cli")
    if not os.path.exists(whisper_cli):
        logger.info("Запуск сборки whisper.cpp (cmake)...")
        success, _ = run_command("cmake -B build", cwd=ASME_WHISPER_DIR)
        if not success:
            logger.error("Ошибка генерации сборочных файлов (cmake).")
            sys.exit(1)
        success, _ = run_command("cmake --build build --config Release", cwd=ASME_WHISPER_DIR)
        if not success:
            logger.error("Ошибка сборки whisper.cpp.")
            sys.exit(1)
    else:
        logger.info("Бинарный файл whisper-cli уже существует, сборка пропущена.")

    logger.info("Команда install выполнена успешно.")
    logger.info("Перед началом работы необходимо вручную настроить Multi-Output Device и Aggregate Device для корректной записи системного звука и микрофона")

def record_command(args):
    """Команда record: запись звука через ffmpeg с параметрами из конфигурации.
    Если файл записи уже существует, запрашивает подтверждение на перезапись."""
    ensure_assist_dir()
    ensure_work_dir()
    config = load_config()

    # Проверка на существование файла записи
    if os.path.exists(ASME_RECORD_FILE):
        answer = input(f"Файл {ASME_RECORD_FILE} уже существует. Перезаписать? (y/n): ").strip().lower()
        if answer != 'y':
            logger.info("Запись отменена пользователем.")
            sys.exit(0)
    
    audio_input_1 = config.get("audio_input_1", DEFAULT_CONFIG["audio_input_1"])
    audio_input_2 = config.get("audio_input_2", DEFAULT_CONFIG["audio_input_2"])

    ffmpeg_cmd = (f'ffmpeg -f avfoundation -i "{audio_input_1}" '
                  f'-f avfoundation -i "{audio_input_2}" '
                  f'-filter_complex amerge=inputs=2 "{ASME_RECORD_FILE}"')
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
    """Команда transcribate: конвертация аудиофайла, транскрибация и сохранение результатов в рабочей директории.
    Перед началом транскрибации запрашивает название сессии и переименовывает директорию WORK_DIR."""
    ensure_assist_dir()
    ensure_work_dir()
    
    if not os.path.exists(ASME_RECORD_FILE):
        logger.error(f"Файл записи {ASME_RECORD_FILE} не найден. Сначала выполните команду record.")
        sys.exit(1)
    
    # Запрос названия сессии у пользователя с проверкой допустимых символов (латинские буквы, цифры, _ и -)
    session_name = input("Введите название для сессии (разрешены латинские буквы, цифры, _ и -): ").strip()
    while not re.fullmatch(r'[A-Za-z0-9_-]+', session_name):
        print("Введено недопустимое название. Повторите ввод.")
        session_name = input("Введите название для сессии: ").strip()
    
    new_session_dir = os.path.join(ASME_DIR, f"session-{session_name}")
    if os.path.exists(new_session_dir):
        logger.error(f"Директория {new_session_dir} уже существует. Выберите другое название.")
        sys.exit(1)
    
    # Переименовываем текущую рабочую директорию в новую сессии
    try:
        os.rename(ASME_WORK_DIR, new_session_dir)
        logger.info(f"Директория сессии переименована в {new_session_dir}")
    except Exception as e:
        logger.error(f"Ошибка переименования директории сессии: {e}")
        sys.exit(1)
    
    # Обновляем глобальные переменные для работы с новыми путями
    TMP_ASME_WORK_DIR = new_session_dir
    TMP_ASME_RECORD_FILE = os.path.join(TMP_ASME_WORK_DIR, "record.mp3")
    TMP_ASME_OUTPUT_FILE = os.path.join(TMP_ASME_WORK_DIR, "output.wav")
    
    # Конвертация аудиофайла
    ffmpeg_conv_cmd = (f'ffmpeg -i "{TMP_ASME_RECORD_FILE}" -af "lowpass=f=4000" '
                       f'-ar 16000 -ac 1 -c:a pcm_s16le "{TMP_ASME_OUTPUT_FILE}"')
    logger.info("Конвертация аудиофайла...")
    success, _ = run_command(ffmpeg_conv_cmd)
    if not success:
        logger.error("Ошибка конвертации файла.")
        sys.exit(1)

    # Запуск транскрибации
    whisper_cli = os.path.join(ASME_WHISPER_DIR, "build", "bin", "whisper-cli")
    model_path = os.path.join(ASME_WHISPER_DIR, "models", "ggml-large-v2.bin")
    if not os.path.exists(whisper_cli):
        logger.error("Бинарный файл whisper-cli не найден. Проверьте, что команда install выполнена успешно.")
        sys.exit(1)
    
    transcribe_cmd = (f'"{whisper_cli}" -t 8 -p 2 -m "{model_path}" '
                      f'-l ru --output-txt -f "{TMP_ASME_OUTPUT_FILE}"')
    logger.info("Запуск транскрибации...")
    success, output = run_command(transcribe_cmd, cwd=TMP_ASME_WORK_DIR)
    if not success:
        logger.error("Ошибка транскрибации.")
        sys.exit(1)
    else:
        logger.info("Транскрибация завершена успешно. Результат:")
        logger.info(output)
        print(output)

    logger.info(f"Временные файлы и результат транскрибации сохранены в {TMP_ASME_WORK_DIR}")

def main():
    parser = argparse.ArgumentParser(description="Assist Me: CLI инструмент для транскрибации на macOS")
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