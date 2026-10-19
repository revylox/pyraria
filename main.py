#!/usr/bin/env python3
# /// script
# dependencies = [
#   "numpy",
# ]
# ///
"""Pyraria - a Terraria-style 2D sandbox.

Desktop:  python main.py
Web:      this file is also the entry point of the pygbag (browser) build.
"""
import asyncio

import numpy  # noqa: F401  (imported here so the web build ships numpy)
import pygame  # noqa: F401

from pyraria.app import WEB, main_async

if WEB or __name__ == "__main__":
    asyncio.run(main_async())
