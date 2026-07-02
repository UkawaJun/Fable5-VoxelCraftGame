"""GL smoke test: boot the real Game window, render frames, then exit.

在虚拟显示器(xvfb)+软件OpenGL下跑真实窗口若干帧，验证渲染/着色器/HUD
不会崩溃。仅用于 CI/沙盒；正常玩游戏直接 python main.py。
"""
import sys
import pyglet
import main as game_main

FRAMES = 240


def run():
    import math
    game = game_main.Game()
    w = game.world
    p = game.player
    state = {"n": 0, "max_debris": 0, "exploded": False}

    # spawn TNT + a slime + a pig right next to the player, rain on
    bx, by, bz = int(p.pos[0]) + 2, int(p.pos[1]), int(p.pos[2])
    sy = w.surface_y(bx, bz) or by
    from content.registry import block_id
    w.set_block(bx, sy + 1, bz, block_id("tnt"))
    from entities.mobs.slime import Slime
    from entities.mobs.pig import Pig
    w.entities.append(Slime((p.pos[0] + 1.5, sy + 2.0, p.pos[2])))
    w.entities.append(Pig((p.pos[0] - 1.5, sy + 2.0, p.pos[2])))
    game.weather.force("RAIN")

    def tick(dt):
        if state["n"] == 20:
            w.ignite_tnt((bx, sy + 1, bz), fuse=0.5)   # -> explosion soon
        game.update(1 / 60.0)
        game.switch_to()
        game.dispatch_event("on_draw")
        game.flip()
        state["max_debris"] = max(state["max_debris"], w.debris.count)
        if any(e.TYPE_NAME == "primed_tnt" for e in w.entities):
            state["exploded"] = True
        state["n"] += 1
        if state["n"] >= FRAMES:
            game._save()
            assert state["exploded"], "TNT never primed"
            assert state["max_debris"] > 0, "explosion produced no debris"
            print(f"[PASS] {state['n']} frames | peak debris="
                  f"{state['max_debris']} | mobs="
                  f"{sum(1 for e in w.entities if e.TYPE_NAME in ('slime','pig'))}"
                  f" | weather={game.weather.state}"
                  f"({game.weather.active_count()} particles)")
            print("[PASS] explosion/debris/weather/mob render OK")
            print("[PASS] GL smoke test OK")
            pyglet.app.exit()

    pyglet.clock.schedule_interval(tick, 1 / 60.0)
    pyglet.app.run()


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
