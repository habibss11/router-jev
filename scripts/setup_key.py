#!/usr/bin/env python3
"""Set OpenRouter credentials using hidden terminal input, never CLI arguments."""
import argparse
import getpass
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
from credentials import credential_status, save_key


def main():
    parser = argparse.ArgumentParser(description="Настройка ключа OpenRouter для Codex Decision Router")
    parser.add_argument("--init", action="store_true", help="Создать пустой файл; сохранить уже существующий")
    parser.add_argument("--status", action="store_true", help="Показать состояние и путь без значения ключа")
    args = parser.parse_args()
    if args.init:
        try:
            path = save_key(None, initialize_only=True)
        except OSError:
            print("Не удалось создать файл ключа. Проверьте права на каталог.", file=sys.stderr)
            return 1
        print(f"Файл для ключа: {path}")
        return 0
    if args.status:
        print(json.dumps(credential_status(), ensure_ascii=False, indent=2))
        return 0
    if not sys.stdin.isatty():
        print("Запустите эту команду в Терминале: требуется скрытый ввод ключа.", file=sys.stderr)
        return 1
    key = getpass.getpass("Вставьте ключ OpenRouter (ввод скрыт): ").strip()
    if not key.startswith("sk-or-"):
        print("Ожидается ключ OpenRouter, начинающийся с sk-or-. Файл не изменён.", file=sys.stderr)
        return 1
    try:
        path = save_key(key)
    except (OSError, ValueError):
        print("Не удалось сохранить ключ. Проверьте формат и права на каталог.", file=sys.stderr)
        return 1
    print(f"Ключ сохранён: {path}")
    print("Маршрутизатор подхватит ключ при следующем вызове.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
