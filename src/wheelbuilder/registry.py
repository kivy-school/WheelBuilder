"""Mapping of anaconda package names → wheel class (mirrors WheelsToBuild.swift)."""
from wheelbuilder.protocols import WheelBase
from wheelbuilder.wheels.cibuildwheel.aiohttp import Aiohttp
from wheelbuilder.wheels.cibuildwheel.apsw import Apsw
from wheelbuilder.wheels.cibuildwheel.bcrypt import Bcrypt
from wheelbuilder.wheels.cibuildwheel.bitarray import Bitarray
from wheelbuilder.wheels.cibuildwheel.blosc2 import Blosc2
from wheelbuilder.wheels.cibuildwheel.cffi import Cffi
from wheelbuilder.wheels.cibuildwheel.contourpy import Contourpy
from wheelbuilder.wheels.cibuildwheel.coverage import Coverage
from wheelbuilder.wheels.cibuildwheel.greenlet import Greenlet
from wheelbuilder.wheels.cibuildwheel.kiwisolver import Kiwisolver
from wheelbuilder.wheels.cibuildwheel.materialyoucolor import Materialyoucolor
from wheelbuilder.wheels.cibuildwheel.matplotlib import Matplotlib
from wheelbuilder.wheels.cibuildwheel.msgpack import Msgpack
from wheelbuilder.wheels.cibuildwheel.netifaces import Netifaces
from wheelbuilder.wheels.cibuildwheel.numpy import Numpy
from wheelbuilder.wheels.cibuildwheel.opencv import Opencv
from wheelbuilder.wheels.cibuildwheel.pandas import Pandas
from wheelbuilder.wheels.cibuildwheel.pillow import Pillow
from wheelbuilder.wheels.cibuildwheel.pycryptodome import Pycryptodome
from wheelbuilder.wheels.cibuildwheel.pymunk import Pymunk
from wheelbuilder.wheels.cibuildwheel.pynacl import Pynacl
from wheelbuilder.wheels.cibuildwheel.regex import Regex
from wheelbuilder.wheels.cibuildwheel.sqlalchemy import SQLAlchemy
from wheelbuilder.wheels.cibuildwheel.zeroconf import Zeroconf
from wheelbuilder.wheels.library.ffmpeg import Ffmpeg
from wheelbuilder.wheels.maturin.cryptography import Cryptography
from wheelbuilder.wheels.maturin.orjson import Orjson
from wheelbuilder.wheels.maturin.pendulum import Pendulum
from wheelbuilder.wheels.maturin.pydantic_core import Pydantic_core


# Packages excluded from the weekly auto-update scheduler.
# Add names here to keep a package in WHEELS (manually buildable)
# but skip it during the weekly --checks run.
_WEEKLY_EXCLUDE = {
    "ffmpeg",
}


def _make_weekly(wheels: dict[str, type[WheelBase]], exclude: set[str]) -> dict[str, type[WheelBase]]:
    return {k: v for k, v in wheels.items() if k not in exclude}


# Anaconda package name → wheel class (None entries omitted)
WHEELS: dict[str, type[WheelBase]] = {
    "aiohttp": Aiohttp,
    "apsw": Apsw,
    "bcrypt": Bcrypt,
    "bitarray": Bitarray,
    "blosc2": Blosc2,
    "cffi": Cffi,
    "contourpy": Contourpy,
    "coverage": Coverage,
    "cryptography": Cryptography,
    "ffmpeg": Ffmpeg,
    "greenlet": Greenlet,
    "kiwisolver": Kiwisolver,
    "materialyoucolor": Materialyoucolor,
    "matplotlib": Matplotlib,
    "msgpack": Msgpack,
    "netifaces": Netifaces,
    "numpy": Numpy,
    "opencv-python": Opencv,
    "orjson": Orjson,
    "pandas": Pandas,
    "pendulum": Pendulum,
    "pillow": Pillow,
    "pycryptodome": Pycryptodome,
    "pydantic_core": Pydantic_core,
    "pymunk": Pymunk,
    "pynacl": Pynacl,
    "regex": Regex,
    "sqlalchemy": SQLAlchemy,
    "zeroconf": Zeroconf,
}


WEEKLY_WHEELS: dict[str, type[WheelBase]] = _make_weekly(WHEELS, _WEEKLY_EXCLUDE)
