"""Chunk: a 16x128x16 numpy block array + bookkeeping flags.

区块 = 连续内存的 numpy uint8 数组（不是 Python 对象字典）——
这是整个引擎"快"的根基：批量运算、零拷贝序列化。
"""

import zlib

import numpy as np

from settings import CHUNK_SX, CHUNK_SY, CHUNK_SZ


class Chunk:
    SX, SY, SZ = CHUNK_SX, CHUNK_SY, CHUNK_SZ
    __slots__ = ("cx", "cz", "blocks", "light", "modified")

    def __init__(self, cx: int, cz: int, blocks: np.ndarray = None):
        self.cx = cx
        self.cz = cz
        if blocks is None:
            blocks = np.zeros((self.SX, self.SY, self.SZ), dtype=np.uint8)
        self.blocks = blocks          # [x, y, z] local coords
        # block-light level 0..15 (萤石等光源传播的结果), derived -> not saved
        self.light = np.zeros((self.SX, self.SY, self.SZ), dtype=np.uint8)
        self.modified = False         # differs from generator output -> save it

    # -- serialisation (zlib-compressed raw bytes) -------------------------
    def to_bytes(self) -> bytes:
        return zlib.compress(self.blocks.tobytes(), level=6)

    @classmethod
    def from_bytes(cls, cx: int, cz: int, data: bytes) -> "Chunk":
        arr = np.frombuffer(zlib.decompress(data), dtype=np.uint8)
        arr = arr.reshape((cls.SX, cls.SY, cls.SZ)).copy()
        c = cls(cx, cz, arr)
        c.modified = True             # came from save -> keep persisting it
        return c
