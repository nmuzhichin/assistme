#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
import shutil
import yaml  # pip install pyyaml
import logging
import re
import json

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

# Значения по умолчанию для аудио-устройств и языка
DEFAULT_CONFIG = {
    "lang": "en",           # язык по умолчанию
    "audio": {
        "input":  ":0",     # микрофон
        "output": ":3"      # системный звук
    }
}

# Путь к JSON-файлу с переводами (находится рядом со скриптом)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRANSLATIONS_FILE = os.path.join(SCRIPT_DIR, "translations.json")

# Создаем необходимые директории до настройки логирования
os.makedirs(ASME_DIR, exist_ok=True)
os.makedirs(ASME_WORK_DIR, exist_ok=True)
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

# Глобальные переменные для i18n
CURRENT_LANG = "en"
TRANSLATIONS = {}

def load_translations(file_path):
    """Загружает переводы из JSON-файла."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading translations: {e}")
        return {}

def get_text(key):
    """Возвращает перевод для заданного ключа с учетом текущего языка."""
    return TRANSLATIONS.get(CURRENT_LANG, {}).get(key, key)

def run_command(cmd, cwd=None):
    """Выполняет системную команду с логированием и проверкой ошибок."""
    logger.info(f"Executing: {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        logger.error(f"Error executing command: {cmd}")
        logger.error(f"stdout:\n{result.stdout}")
        logger.error(f"stderr:\n{result.stderr}")
        return False, result.stdout + result.stderr
    logger.info(f"Command executed successfully: {cmd}")
    return True, result.stdout

def check_brew():
    """Проверяет наличие Homebrew в системе."""
    if shutil.which("brew") is None:
        logger.error(get_text("brew_not_found"))
        return False
    logger.info(get_text("brew_found"))
    return True

def ensure_directory(path):
    """Создает указанную директорию, если она не существует."""
    if not os.path.isdir(path):
        os.makedirs(path)
        logger.info(get_text("assist_dir_created").format(path))

def ensure_assist_dir():
    """Создает директорию .assistme в домашней папке."""
    ensure_directory(ASME_DIR)

def ensure_work_dir():
    """Создает поддиректорию для временных файлов и результатов транскрибации."""
    ensure_directory(ASME_WORK_DIR)

def load_config():
    """Загружает конфигурацию из YAML-файла, создавая дефолтную при отсутствии."""
    if not os.path.exists(ASME_CONFIG_FILE):
        logger.info("Configuration file not found, creating default.")
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    try:
        with open(ASME_CONFIG_FILE, "r") as f:
            config = yaml.safe_load(f)
            if not config:
                config = DEFAULT_CONFIG
    except Exception as e:
        logger.error(f"Error reading configuration file: {e}")
        config = DEFAULT_CONFIG
    return config

def save_config(config):
    """Сохраняет конфигурацию в YAML-файл."""
    with open(ASME_CONFIG_FILE, "w") as f:
        yaml.dump(config, f)
    logger.info(f"Configuration saved in {ASME_CONFIG_FILE}")

def install_command(args):
    """Команда install: установка Homebrew, ffmpeg, blackhole, клонирование и сборка whisper.cpp."""
    if not check_brew():
        sys.exit(1)
    
    for pkg in ["ffmpeg", "blackhole-16ch"]:
        logger.info(get_text("installing_pkg").format(pkg))
        success, _ = run_command(f"brew install {pkg}")
        if not success:
            logger.error(get_text("install_pkg_error").format(pkg))
            sys.exit(1)
    
    ensure_assist_dir()
    ensure_work_dir()

    if not os.path.isdir(ASME_WHISPER_DIR):
        logger.info(get_text("cloning_whisper"))
        success, _ = run_command(f"git clone https://github.com/ggerganov/whisper.cpp.git {ASME_WHISPER_DIR}")
        if not success:
            logger.error("Error cloning whisper.cpp.")
            sys.exit(1)
    else:
        logger.info(get_text("whisper_exists"))

    model_file = os.path.join(ASME_WHISPER_DIR, "models", "ggml-large-v2.bin")
    if not os.path.exists(model_file):
        logger.info(get_text("downloading_model"))
        success, _ = run_command("sh ./models/download-ggml-model.sh large-v2", cwd=ASME_WHISPER_DIR)
        if not success:
            logger.error("Error downloading model.")
            sys.exit(1)
    else:
        logger.info(get_text("model_exists"))

    whisper_cli = os.path.join(ASME_WHISPER_DIR, "build", "bin", "whisper-cli")
    if not os.path.exists(whisper_cli):
        logger.info(get_text("building_whisper"))
        success, _ = run_command("cmake -B build", cwd=ASME_WHISPER_DIR)
        if not success:
            logger.error(get_text("build_error"))
            sys.exit(1)
        success, _ = run_command("cmake --build build --config Release", cwd=ASME_WHISPER_DIR)
        if not success:
            logger.error(get_text("build_error"))
            sys.exit(1)
    else:
        logger.info(get_text("whisper_exists"))
    
    logger.info(get_text("install_success"))
    logger.info(get_text("manual_setup_notice"))

def record_command(args):
    """Команда record: запись звука через ffmpeg с параметрами из конфигурации.
    Если файл записи уже существует, запрашивает подтверждение на перезапись."""
    ensure_assist_dir()
    ensure_work_dir()
    config = load_config()

    if os.path.exists(ASME_RECORD_FILE):
        answer = input(get_text("file_exists").format(ASME_RECORD_FILE)).strip().lower()
        if answer != 'y':
            logger.info(get_text("record_cancelled"))
            sys.exit(0)
    
    audio = config.get("audio", DEFAULT_CONFIG["audio"])
    audio_input = audio.get("input")
    audio_output = audio.get("output")

    ffmpeg_cmd = (f'ffmpeg -f avfoundation -i "{audio_input}" '
                  f'-f avfoundation -i "{audio_output}" '
                  f'-filter_complex amerge=inputs=2 "{ASME_RECORD_FILE}"')
    logger.info(get_text("recording"))
    try:
        subprocess.run(ffmpeg_cmd, shell=True, check=True)
    except KeyboardInterrupt:
        logger.info(get_text("record_cancelled"))
    except subprocess.CalledProcessError as e:
        logger.error(get_text("record_error"))
        logger.error(e)
        sys.exit(1)

def transcribate_command(args):
    """Команда transcribate: конвертация аудиофайла, транскрибация и сохранение результатов.
    Перед транскрибацией запрашивает название сессии и переименовывает рабочую директорию."""
    ensure_assist_dir()
    ensure_work_dir()
    
    if not os.path.exists(ASME_RECORD_FILE):
        logger.error(f"Recording file {ASME_RECORD_FILE} not found. Run the record command first.")
        sys.exit(1)
    
    session_name = input(get_text("session_prompt")).strip()
    while not re.fullmatch(r'[A-Za-z0-9_-]+', session_name):
        print(get_text("invalid_session"))
        session_name = input(get_text("session_prompt")).strip()
    
    new_session_dir = os.path.join(ASME_DIR, f"session-{session_name}")
    if os.path.exists(new_session_dir):
        logger.error(get_text("session_exists").format(new_session_dir))
        sys.exit(1)
    
    try:
        os.rename(ASME_WORK_DIR, new_session_dir)
        logger.info(get_text("session_renamed").format(new_session_dir))
    except Exception as e:
        logger.error(get_text("session_rename_error").format(e))
        sys.exit(1)
    
    TMP_ASME_WORK_DIR = new_session_dir
    TMP_ASME_RECORD_FILE = os.path.join(TMP_ASME_WORK_DIR, "record.mp3")
    TMP_ASME_OUTPUT_FILE = os.path.join(TMP_ASME_WORK_DIR, "output.wav")
    
    ffmpeg_conv_cmd = (f'ffmpeg -i "{TMP_ASME_RECORD_FILE}" -af "lowpass=f=4000" '
                       f'-ar 16000 -ac 1 -c:a pcm_s16le "{TMP_ASME_OUTPUT_FILE}"')
    logger.info(get_text("conversion_started"))
    success, _ = run_command(ffmpeg_conv_cmd)
    if not success:
        logger.error(get_text("conversion_error"))
        sys.exit(1)
    
    whisper_cli = os.path.join(ASME_WHISPER_DIR, "build", "bin", "whisper-cli")
    model_path = os.path.join(ASME_WHISPER_DIR, "models", "ggml-large-v2.bin")
    if not os.path.exists(whisper_cli):
        logger.error("whisper-cli binary not found. Ensure the install command was successful.")
        sys.exit(1)
    
    transcribe_cmd = (f'"{whisper_cli}" -t 8 -p 2 -m "{model_path}" '
                      f'-l ru --output-txt -f "{TMP_ASME_OUTPUT_FILE}"')
    logger.info(get_text("transcription_started"))
    success, output = run_command(transcribe_cmd, cwd=TMP_ASME_WORK_DIR)
    if not success:
        logger.error(get_text("transcription_error"))
        sys.exit(1)
    else:
        logger.info(get_text("transcription_success"))
        logger.info(output)
        print(get_text("transcription_success"))
        print(output)
    
    logger.info(get_text("files_saved").format(TMP_ASME_WORK_DIR))

def get_version():
    return 'debug'

def set_setting(arg):
    for n in arg.kv:
        k, v = n.split("=")
        # todo: save to yaml

def main():
    # Предварительный разбор для определения языка
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("-l", "--language", choices=["en", "ru"], help="")
    pre_args, _ = pre_parser.parse_known_args()
    
    config = load_config()
    global CURRENT_LANG, TRANSLATIONS
    CURRENT_LANG = pre_args.language or config.get("lang", "en")
    TRANSLATIONS = load_translations(TRANSLATIONS_FILE)
    if CURRENT_LANG not in TRANSLATIONS:
        CURRENT_LANG = "en"
    
    # Создание основного парсера с локализованными описаниями
    parser = argparse.ArgumentParser(description=get_text("cli_description"), add_help=False)

    opt_group = parser.add_argument_group(get_text("options_help"))
    opt_group.add_argument('-l', '--language', choices=["en", "ru"], help=get_text("lang_help"))
    opt_group.add_argument('-h', '--help', action='help', default=argparse.SUPPRESS, help=get_text("help_help"))
    opt_group.add_argument('-v', '--version', action='version', version=get_version(), help=get_text("version_help"))
    
    # Первый уровень
    subparsers = parser.add_subparsers(dest="command", help="", title=get_text("commands_help"), metavar="")

    parser_record = subparsers.add_parser("record", help=get_text("record_help"))
    parser_record.set_defaults(func=record_command)
    
    parser_transcribate = subparsers.add_parser("transcribate", help=get_text("transcribate_help"))
    parser_transcribate.set_defaults(func=transcribate_command)
    
    # Второй уровень
    parser_env = subparsers.add_parser("env", help=get_text("env_help"), add_help=False)
    env_ops_group = parser_env.add_argument_group(get_text("options_help"))
    env_ops_group.add_argument('-h', '--help', action='help', default=argparse.SUPPRESS, help=get_text("help_help"))
    
    sys_subparsers = parser_env.add_subparsers(dest="command", help="", title=get_text("commands_help"), metavar="")
    parser_install = sys_subparsers.add_parser("install", help=get_text("install_help"))
    parser_install.set_defaults(func=install_command)

    parser_setting_setter = sys_subparsers.add_parser("set", help="set setting")
    parser_setting_setter.add_argument(dest="kv", help="set key=value", nargs="...")
    parser_setting_setter.set_defaults(func=set_setting)
    

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)
    else:
        args.func(args)

if __name__ == "__main__":
    main()