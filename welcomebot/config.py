from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import yaml


@dataclass
class Config(object):
    server: str
    nickname: str
    username: str
    realname: str
    channels: Dict[str, str]

    sasl: Optional[Tuple[str, str]]
    database: Path


def load(filepath: str):
    with open(filepath) as file:
        config_yaml = yaml.safe_load(file.read())

    nickname = config_yaml["nickname"]

    sasl: Optional[Tuple[str, str]] = None
    if "sasl" in config_yaml:
        sasl = (config_yaml["sasl"]["username"], config_yaml["sasl"]["password"])

    return Config(
        config_yaml["server"],
        nickname,
        config_yaml.get("username", nickname),
        config_yaml.get("realname", nickname),
        config_yaml["channels"],
        sasl,
        Path(config_yaml["database"]).expanduser(),
    )
