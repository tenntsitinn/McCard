"""本地点单方案库，使用 Python 标准库运行。"""

import argparse
import json
import sqlite3
from pathlib import Path
from availability import validate_item

DEFAULT_DB = Path(__file__).resolve().parent / "data" / "presets.sqlite3"
MAX_PRESETS = 16
CARD_FACES = (
    "burger-v1", "wings-two-v1", "icecream-three-v2", "nuggets-four-v2",
    "hashbrown-five-v2", "pies-six", "fries-seven", "mcflurry-eight",
    "cola-nine", "chicken-ten", "ronald-king-v1", "birdie-king-v2",
    "hamburglar-king-v1", "grimace-king-v2", "ronald-plaster-v1",
    "ronald-front-v2",
)


class PresetStore:
    def __init__(self, path=DEFAULT_DB):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS presets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                tag TEXT NOT NULL,
                items TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            )"""
        )
        columns = {row[1] for row in self.connection.execute("PRAGMA table_info(presets)")}
        if "face" not in columns:
            self.connection.execute("ALTER TABLE presets ADD COLUMN face TEXT")
        rows = self.connection.execute(
            "SELECT id, face FROM presets ORDER BY id"
        ).fetchall()
        used = {row["face"] for row in rows if row["face"] in CARD_FACES}
        available = iter(face for face in CARD_FACES if face not in used)
        for index, row in enumerate(rows):
            if row["face"] not in CARD_FACES:
                face = next(available, CARD_FACES[index % len(CARD_FACES)])
                self.connection.execute(
                    "UPDATE presets SET face=? WHERE id=?", (face, row["id"])
                )
        self.connection.commit()

    def close(self):
        self.connection.close()

    def save(self, name, items, tag=""):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("方案名称不能为空。")
        if not isinstance(tag, str):
            raise ValueError("标签必须是文本。")
        if not isinstance(items, list) or not items:
            raise ValueError("方案至少需要一个餐品。")
        normalized = []
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("餐品必须包含名称和数量。")
            item_name = item.get("name")
            quantity = item.get("quantity", 1)
            if not isinstance(item_name, str) or not item_name.strip():
                raise ValueError("餐品名称不能为空。")
            if type(quantity) is not int or quantity < 1:
                raise ValueError("餐品数量必须为正整数。")
            normalized.append(validate_item(dict(item, name=item_name.strip(), quantity=quantity)))
        # 写锁覆盖计数和插入，避免多个进程同时保存时超过上限。
        with self.connection:
            self.connection.execute("BEGIN IMMEDIATE")
            count = self.connection.execute("SELECT COUNT(*) FROM presets").fetchone()[0]
            if count >= MAX_PRESETS:
                raise ValueError(f"最多保存 {MAX_PRESETS} 个方案，请先删除一个方案。")
            face = self.next_face()
            cursor = self.connection.execute(
                "INSERT INTO presets (name, tag, items, face) VALUES (?, ?, ?, ?)",
                (name.strip(), tag.strip(), json.dumps(normalized, ensure_ascii=False), face),
            )
            return cursor.lastrowid

    def next_face(self):
        used = {row[0] for row in self.connection.execute(
            "SELECT face FROM presets WHERE face IS NOT NULL")}
        return next((face for face in CARD_FACES if face not in used), CARD_FACES[0])

    def list(self):
        rows = self.connection.execute("SELECT * FROM presets ORDER BY id").fetchall()
        return [dict(row) | {"items": json.loads(row["items"])} for row in rows]

    def delete(self, preset_id):
        with self.connection:
            cursor = self.connection.execute("DELETE FROM presets WHERE id = ?", (preset_id,))
        return cursor.rowcount > 0


def main():
    parser = argparse.ArgumentParser(description=f"常用点单方案库（最多 {MAX_PRESETS} 个）")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="本地数据库路径")
    commands = parser.add_subparsers(dest="command", required=True)
    save = commands.add_parser("save", help="保存点单方案")
    save.add_argument("--name", required=True, help="方案名称")
    save.add_argument("--tag", default="", help="自定义标签，可留空")
    save.add_argument(
        "--item", nargs=2, action="append", required=True,
        metavar=("餐品名称", "数量"), help="可重复传入，例如 --item 巨无霸 1",
    )
    commands.add_parser("list", help="查看所有方案")
    delete = commands.add_parser("delete", help="按编号删除方案")
    delete.add_argument("id", type=int)
    args = parser.parse_args()
    store = None
    try:
        store = PresetStore(args.db)
        if args.command == "save":
            try:
                items = [{"name": name, "quantity": int(quantity)} for name, quantity in args.item]
            except ValueError:
                raise ValueError("餐品数量必须为正整数。") from None
            preset_id = store.save(args.name, items, args.tag)
            print(f"已保存方案 #{preset_id}。")
        elif args.command == "list":
            presets = store.list()
            print(f"已保存 {len(presets)}/{MAX_PRESETS} 个方案")
            for preset in presets:
                print(f"\n#{preset['id']} {preset['name']} | 标签：{preset['tag'] or '未设置'}")
                for item in preset["items"]:
                    print(f"  {item['name']} × {item['quantity']}")
        elif store.delete(args.id):
            print(f"已删除方案 #{args.id}。")
        else:
            raise ValueError(f"方案 #{args.id} 不存在。")
    except (ValueError, sqlite3.Error, OSError) as exc:
        parser.exit(1, f"错误：{exc}\n")
    finally:
        if store is not None:
            store.close()


if __name__ == "__main__":
    main()
