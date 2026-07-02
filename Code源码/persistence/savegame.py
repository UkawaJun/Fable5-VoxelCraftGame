"""SQLite save database. 本地存档数据库（差量保存）。

Tables:
  meta(key, value)            seed / time / weather / version (JSON values)
  chunks(cx, cz, data)        zlib-compressed numpy bytes, ONLY modified chunks
  player(id, data)            position / rotation / hotbar slot (JSON)
  entities(id, type, data)    mobs, primed TNT, debris (JSON)

未修改区块不存盘（由种子按需重算）—— 存档体积极小。
"""

import json
import os
import sqlite3

from content.registry import ENTITY_TYPES
from entities.tnt import PrimedTNT

SAVE_VERSION = 1


class SaveGame:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.path = path
        self.db = sqlite3.connect(path)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS meta(
                key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS chunks(
                cx INTEGER, cz INTEGER, data BLOB,
                PRIMARY KEY(cx, cz));
            CREATE TABLE IF NOT EXISTS player(
                id INTEGER PRIMARY KEY, data TEXT);
            CREATE TABLE IF NOT EXISTS entities(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT, data TEXT);
        """)
        self.db.commit()

    # -- meta ---------------------------------------------------------------
    def get_meta(self, key, default=None):
        row = self.db.execute(
            "SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_meta(self, key, value):
        self.db.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)",
            (key, json.dumps(value)))

    @property
    def exists(self) -> bool:
        return self.get_meta("seed") is not None

    # -- chunks ----------------------------------------------------------------
    def load_chunk(self, cx, cz):
        row = self.db.execute(
            "SELECT data FROM chunks WHERE cx=? AND cz=?", (cx, cz)).fetchone()
        return row[0] if row else None

    def save_chunk(self, chunk):
        self.db.execute(
            "INSERT OR REPLACE INTO chunks(cx, cz, data) VALUES(?, ?, ?)",
            (chunk.cx, chunk.cz, chunk.to_bytes()))
        self.db.commit()

    # -- full save -------------------------------------------------------------
    def save_all(self, world, player, time_system, weather):
        cur = self.db.cursor()
        self.set_meta("seed", world.seed)
        self.set_meta("version", SAVE_VERSION)
        self.set_meta("time", time_system.serialize())
        self.set_meta("weather", weather.serialize())
        for c in world.chunks.values():
            if c.modified:
                cur.execute(
                    "INSERT OR REPLACE INTO chunks(cx, cz, data) VALUES(?,?,?)",
                    (c.cx, c.cz, c.to_bytes()))
        cur.execute("INSERT OR REPLACE INTO player(id, data) VALUES(1, ?)",
                    (json.dumps(player.serialize()),))
        cur.execute("DELETE FROM entities")
        for e in world.entities:
            cur.execute("INSERT INTO entities(type, data) VALUES(?, ?)",
                        (e.TYPE_NAME, json.dumps(e.serialize())))
        for d in world.debris.serialize():
            cur.execute("INSERT INTO entities(type, data) VALUES(?, ?)",
                        ("debris", json.dumps(d)))
        self.db.commit()

    # -- full load ---------------------------------------------------------------
    def load_player_into(self, player) -> bool:
        row = self.db.execute("SELECT data FROM player WHERE id=1").fetchone()
        if not row:
            return False
        player.deserialize(json.loads(row[0]))
        return True

    def load_entities_into(self, world):
        for type_name, data in self.db.execute(
                "SELECT type, data FROM entities"):
            d = json.loads(data)
            if type_name == "debris":
                world.debris.spawn(d["bid"], d["pos"], d["vel"])
            elif type_name == "primed_tnt":
                e = PrimedTNT((0, 0, 0))
                e.deserialize(d)
                world.entities.append(e)
            elif type_name in ENTITY_TYPES:
                e = ENTITY_TYPES[type_name]((0, 0, 0))
                e.deserialize(d)
                world.entities.append(e)

    def close(self):
        self.db.commit()
        self.db.close()
