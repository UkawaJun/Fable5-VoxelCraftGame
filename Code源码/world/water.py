"""MC-style flowing water (cellular automaton). 流动水模拟。

水位：源 water=8（永不枯竭），流动 water1..7。从源水平最远流 7 格；
落水（上方有水）重置为满流，可一直往下流。两个相邻源之间的格子会变成新源
（无限水机制）。

性能：只处理"活跃水格队列"，每帧有预算；水静止后队列清空 -> 零开销。
水流模拟自己调用 set_block(water=False) 避免递归入队。
"""

from content.fluids import (FLUID_LEVEL, FLUID_LUT, LEVEL_TO_ID,
                            SOURCE_ID, SOURCE_LEVEL)

_H = ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1))   # 4 horizontal neighbours


def _outflow(level: int) -> int:
    """Level this fluid hands to a horizontal neighbour. 源给7，流动给 L-1。"""
    if level >= SOURCE_LEVEL:
        return SOURCE_LEVEL - 1
    return level - 1 if level > 1 else 0


def _target_level(world, x, y, z) -> int:
    """Desired fluid level for an air/flowing cell (0 = should be dry)."""
    target = 0
    if FLUID_LUT[world.get_block(x, y + 1, z)]:        # water above -> falls full
        target = SOURCE_LEVEL - 1
    for dx, _, dz in _H:
        nb = world.get_block(x + dx, y, z + dz)
        if FLUID_LUT[nb]:
            eo = _outflow(int(FLUID_LEVEL[nb]))
            if eo > target:
                target = eo
    return target


def enqueue(world, x, y, z):
    """Queue a cell and its 6 neighbours for re-evaluation."""
    q = world.water_queue
    q.append((x, y, z))
    q.append((x, y - 1, z))
    q.append((x, y + 1, z))
    for dx, _, dz in _H:
        q.append((x + dx, y, z + dz))


def near_water(world, x, y, z) -> bool:
    """Is any of the 6 neighbours fluid? (cheap gate before enqueueing)"""
    if FLUID_LUT[world.get_block(x, y + 1, z)] or FLUID_LUT[world.get_block(x, y - 1, z)]:
        return True
    for dx, _, dz in _H:
        if FLUID_LUT[world.get_block(x + dx, y, z + dz)]:
            return True
    return False


def process(world, budget: int):
    q = world.water_queue
    n = 0
    while q and n < budget:
        x, y, z = q.popleft()
        n += 1
        if not world.is_loaded(x, z):
            continue
        cur = int(world.get_block(x, y, z))
        if cur == SOURCE_ID:
            continue                                   # sources are permanent
        cur_lvl = int(FLUID_LEVEL[cur])
        if cur != 0 and cur_lvl == 0:
            continue                                   # a solid block sits here

        # infinite water: >=2 horizontal source neighbours -> become a source
        src = 0
        for dx, _, dz in _H:
            if world.get_block(x + dx, y, z + dz) == SOURCE_ID:
                src += 1
        if src >= 2:
            world.set_block(x, y, z, SOURCE_ID, notify=False, light=False, water=False)
            enqueue(world, x, y, z)
            continue

        target = _target_level(world, x, y, z)
        if cur == 0:                                   # empty cell
            if target >= 1:
                world.set_block(x, y, z, LEVEL_TO_ID[target],
                                notify=False, light=False, water=False)
                enqueue(world, x, y, z)
        else:                                          # flowing water
            if target < 1:
                world.set_block(x, y, z, 0, notify=False, light=False, water=False)
                enqueue(world, x, y, z)
            elif target != cur_lvl:
                world.set_block(x, y, z, LEVEL_TO_ID[target],
                                notify=False, light=False, water=False)
                enqueue(world, x, y, z)
