"""Terminal presentation. Kept away from the rules so the engine stays testable."""

import os
import sys

_ANSI = True


def init():
    """Turn on virtual terminal processing so ANSI works in older consoles."""
    global _ANSI
    if os.name == "nt":
        try:
            import ctypes
            k = ctypes.windll.kernel32
            k.SetConsoleMode(k.GetStdHandle(-11), 7)
            os.system("")
        except Exception:
            _ANSI = False
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


C = {
    "reset": "\033[0m", "dim": "\033[2m", "bold": "\033[1m",
    "red": "\033[31m", "green": "\033[32m", "yellow": "\033[33m",
    "blue": "\033[34m", "magenta": "\033[35m", "cyan": "\033[36m",
    "white": "\033[37m", "grey": "\033[90m",
    "bred": "\033[91m", "bgreen": "\033[92m", "byellow": "\033[93m",
    "bcyan": "\033[96m",
}


def c(text, *styles):
    if not _ANSI:
        return str(text)
    return "".join(C.get(s, "") for s in styles) + str(text) + C["reset"]


def rule(char="-", width=68):
    print(c(char * width, "grey"))


def header(title, subtitle=None):
    print()
    print(c(title.upper(), "bold", "bcyan"))
    if subtitle:
        print(c(subtitle, "grey"))
    rule()


def bar(value, maximum, width=18, style="green", warn_below=0.35):
    if maximum <= 0:
        maximum = 1
    frac = max(0.0, min(1.0, value / maximum))
    filled = int(round(frac * width))
    if frac <= warn_below:
        style = "bred"
    elif frac <= 0.6 and style == "green":
        style = "byellow"
    return c("#" * filled, style) + c("." * (width - filled), "grey")


def field(label, value, width=13):
    return f"{c(label.ljust(width), 'grey')}{value}"


def say(lines):
    if isinstance(lines, str):
        lines = [lines]
    for line in lines:
        if line == "__FLED__":
            continue
        if not line:
            print()
        elif line.startswith("["):
            print(c(line, "bcyan"))
        else:
            print(f"  {line}")


def menu(options, prompt="> "):
    """options: list of (key, label, enabled, note). Returns chosen key."""
    print()
    for key, label, enabled, note in options:
        tag = c(f" [{key}]", "bold" if enabled else "grey")
        text = label if enabled else c(label, "grey")
        suffix = c(f"  {note}", "grey") if note else ""
        print(f"{tag} {text}{suffix}")
    valid = {k.lower() for k, _, en, _ in options if en}
    while True:
        try:
            choice = input(c(prompt, "bcyan")).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "q"
        if choice in valid:
            return choice
        print(c("  Not an option.", "grey"))


def pause():
    try:
        input(c("\n  ...", "grey"))
    except (EOFError, KeyboardInterrupt):
        pass


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def ordinal(n):
    n = int(n)
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }".replace(" ", "")
