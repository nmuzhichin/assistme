#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
import shutil
import yaml  # требуется установить PyYAML (pip install pyyaml)

# Пути к директории и файлам настроек
HOME_DIR = os.path.expanduser("~")
ASSIST_DIR = os.path.join(HOME_DIR, ".assistme")
CONFIG_FILE = os.path.join(ASSIST_DIR, "config.yaml")
WHISPER_DIR = os.path.join(ASSIST_DIR, "whisper.cpp")
RECORD_FILE = "record.mp3"
OUTPUT_FILE = "output.wav"

# Значения по умолчанию для аудиоустройств
DEFAULT_CONFIG = {
    "audio_input_1": ":0",   # обычно микрофон
    "audio_input_2": ":3"    # обычно системный звук через BlackHole 16ch
}

def run_command(cmd, cwd=None):
    """Вспомогательная функция для выполнения системных команд с выводом статуса."""
    print(f"Выполнение: {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print(f"Ошибка выполнения команды: {cmd}")
        print(f"Стандартный вывод:\n{result.stdout}")
        print(f"Стандартный поток ошибок:\n{result.stderr}")
        return False, result.stdout + result.stderr
    return True, result.stdout

def check_brew():
    """Проверяет наличие Homebrew в системе."""
    result = shutil.which("brew")
    if result is None:
        print("Homebrew не найден. Пожалуйста, установите Homebrew с https://brew.sh/")
        return False
    return True

def ensure_assist_dir():
    """Создает директорию .assistme в домашней папке, если она не существует."""
    if not os.path.isdir(ASSIST_DIR):
        os.makedirs(ASSIST_DIR)
        print(f"Создана директория: {ASSIST_DIR}")

def load_config():
    """Загружает конфигурационный YAML-файл. Если его нет, создает с дефолтными настройками."""
    if not os.path.exists(CONFIG_FILE):
        print("Конфигурационный файл не найден, создаю дефолтный.")
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    with open(CONFIG_FILE, "r") as f:
        try:
            config = yaml.safe_load(f)
            if not config:
                config = DEFAULT_CONFIG
        except Exception as e:
            print(f"Ошибка чтения конфигурационного файла: {e}")
            config = DEFAULT_CONFIG
    return config

def save_config(config):
    """Сохраняет конфигурацию в YAML-файл."""
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f)
    print(f"Конфигурация сохранена в {CONFIG_FILE}")

def install_command(args):
    """Команда install: проверяет наличие Homebrew, устанавливает ffmpeg и blackhole, клонирует и собирает whisper.cpp."""
    # Проверка наличия Homebrew
    if not check_brew():
        sys.exit(1)
    
    # Установка ffmpeg и blackhole-16ch через brew
    for pkg in ["ffmpeg", "blackhole-16ch"]:
        print(f"Устанавливаю {pkg} через brew...")
        success, _ = run_command(f"brew install {pkg}")
        if not success:
            print(f"Ошибка установки {pkg}. Прерывание установки.")
            sys.exit(1)
    
    # Создаем директорию .assistme
    ensure_assist_dir()

    # Клонирование репозитория whisper.cpp, если он не существует
    if not os.path.isdir(WHISPER_DIR):
        print("Клонирование репозитория whisper.cpp...")
        success, _ = run_command(f"git clone https://github.com/ggerganov/whisper.cpp.git {WHISPER_DIR}")
        if not success:
            print("Ошибка клонирования whisper.cpp.")
            sys.exit(1)
    else:
        print("Репозиторий whisper.cpp уже существует, пропускаю клонирование.")

    # Переходим в директорию whisper.cpp
    # Скачиваем модель large-v2
    print("Скачивание модели ggml-large-v2...")
    success, _ = run_command("sh ./models/download-ggml-model.sh large-v2", cwd=WHISPER_DIR)
    if not success:
        print("Ошибка скачивания модели.")
        sys.exit(1)

    # Билдим проект
    print("Запуск сборки whisper.cpp (cmake)...")
    success, _ = run_command("cmake -B build", cwd=WHISPER_DIR)
    if not success:
        print("Ошибка генерации сборочных файлов (cmake).")
        sys.exit(1)
    success, _ = run_command("cmake --build build --config Release", cwd=WHISPER_DIR)
    if not success:
        print("Ошибка сборки whisper.cpp.")
        sys.exit(1)

    print("Команда install выполнена успешно.")

def record_command(args):
    """Команда record: записывает звук с использованием ffmpeg с параметрами из конфигурационного файла."""
    # Загружаем или создаем конфигурационный файл
    ensure_assist_dir()
    config = load_config()

    audio_input_1 = config.get("audio_input_1", DEFAULT_CONFIG["audio_input_1"])
    audio_input_2 = config.get("audio_input_2", DEFAULT_CONFIG["audio_input_2"])

    # Формирование команды для записи
    ffmpeg_cmd = (f'ffmpeg -f avfoundation -i "{audio_input_1}" '
                  f'-f avfoundation -i "{audio_input_2}" '
                  f'-filter_complex amerge=inputs=2 {RECORD_FILE}')
    print("Запуск записи звука. Для остановки записи используйте Ctrl+C.")
    try:
        # Передача управления в ffmpeg, вывод в консоль
        subprocess.run(ffmpeg_cmd, shell=True, check=True)
    except KeyboardInterrupt:
        print("\nЗапись остановлена пользователем.")
    except subprocess.CalledProcessError as e:
        print("Ошибка записи звука:")
        print(e)
        sys.exit(1)

def transcribate_command(args):
    """Команда transcribate: конвертирует аудиофайл, запускает транскрибацию и удаляет временные файлы."""
    # Проверка существования записанного файла
    if not os.path.exists(RECORD_FILE):
        print(f"Файл {RECORD_FILE} не найден. Сначала выполните команду record.")
        sys.exit(1)
    
    # Конвертация record.mp3 в output.wav
    ffmpeg_conv_cmd = (f'ffmpeg -i {RECORD_FILE} -af "lowpass=f=4000" '
                       f'-ar 16000 -ac 1 -c:a pcm_s16le {OUTPUT_FILE}')
    print("Конвертация аудиофайла...")
    success, _ = run_command(ffmpeg_conv_cmd)
    if not success:
        print("Ошибка конвертации файла.")
        sys.exit(1)

    # Формирование команды для транскрибации
    whisper_cli = os.path.join(WHISPER_DIR, "build", "bin", "whisper-cli")
    model_path = os.path.join(WHISPER_DIR, "models", "ggml-large-v2.bin")
    if not os.path.exists(whisper_cli):
        print("Бинарный файл whisper-cli не найден. Проверьте, что команда install выполнена успешно.")
        sys.exit(1)
    transcribe_cmd = (f'{whisper_cli} -t 8 -p 2 -m {model_path} '
                      f'-l ru --output-txt -f {OUTPUT_FILE}')
    print("Запуск транскрибации...")
    success, output = run_command(transcribe_cmd)
    if not success:
        print("Ошибка транскрибации.")
        sys.exit(1)
    else:
        print("Транскрибация завершена успешно. Результат:\n")
        print(output)

    # Удаляем временные файлы
    try:
        os.remove(RECORD_FILE)
        os.remove(OUTPUT_FILE)
        print("Временные файлы удалены.")
    except Exception as e:
        print(f"Ошибка удаления временных файлов: {e}")

def main():
    parser = argparse.ArgumentParser(description="Assistme: CLI инструмент транскрибации на macOS")
    subparsers = parser.add_subparsers(dest="command", help="Доступные команды")

    # Подкоманда install
    parser_install = subparsers.add_parser("install", help="Установка зависимостей")
    parser_install.set_defaults(func=install_command)

    # Подкоманда record
    parser_record = subparsers.add_parser("record", help="Записывает звук через ffmpeg")
    parser_record.set_defaults(func=record_command)

    # Подкоманда transcribate
    parser_transcribate = subparsers.add_parser("transcribate", help="Конвертирует запись и выполняет транскрибацию")
    parser_transcribate.set_defaults(func=transcribate_command)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)
    else:
        args.func(args)

if __name__ == "__main__":
    main()