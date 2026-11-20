import json
from importlib.resources import files
from string import Formatter

from aiogram.utils.formatting import Text

with files(__package__).joinpath("ru.json").open(encoding="utf-8") as stream:
    _phrases = json.load(stream)


def phrase(key: str) -> str:
    group, name = key.split(".")
    return _phrases[group][name]


def rich_phrase(key: str, **fields) -> Text:
    parts = []
    for literal, field, _, _ in Formatter().parse(phrase(key)):
        parts.append(literal)
        if field is not None:
            parts.append(fields[field])
    return Text(*parts)
