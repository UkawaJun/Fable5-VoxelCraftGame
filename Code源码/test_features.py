"""Headless tests for the new features: lighting / combat / sprint / flight /
new blocks. Run: python test_features.py"""
import math, sys, time
import numpy as np
import content.blocks, content.items
import entities.mobs.slime, entities.mobs.pig
from world.world import World
from content.registry import BLOCK_BY_NAME, block_id
from entities.player import Player
from entities.mobs.slime import Slime
from entities.mobs.pig import Pig

P = 0
def check(name, cond):
    global P
    print(f"[{'PASS' if cond else 'FAIL'}] {name}", flush=True)
    if not cond: sys.exit(1)
    P += 1

def ready_world(seed=4242):
    w = World(seed); w.ensure_chunks_around(8, 8)
    t = time.time()
    while w._pending and time.time()-t < 20:
        w.process_gen_results(budget=200); time.sleep(0.005)
    return w

def step(w, secs, dt=1/60):
    for _ in range(int(secs/dt)):
        w.update_entities(dt); w.process_block_updates(); w.process_light_updates(budget=999)

def main():
    # ---------- new blocks ----------
    for nm in ["cobblestone","mossy_cobble","gravel","bricks","bookshelf",
               "jack_o_lantern","lantern","gold_block","diamond_block",
               "obsidian","redstone_lamp"]:
        check(f"block '{nm}' registered", nm in BLOCK_BY_NAME)
    lights = [n for n,b in BLOCK_BY_NAME.items() if b.emissive>0]
    check("4 light sources", set(lights)=={"glowstone","jack_o_lantern","lantern","redstone_lamp"})
    check("gravel is gravity block", BLOCK_BY_NAME["gravel"].gravity_affected)
    check("obsidian blast-resistant", BLOCK_BY_NAME["obsidian"].blast_resistance > 1000)

    w = ready_world()
    sy = w.surface_y(8,8)

    # ---------- lighting: each light source illuminates, removal clears ----------
    for lname, exp in [("glowstone",15),("jack_o_lantern",15),
                       ("lantern",14),("redstone_lamp",15)]:
        w.set_block(8, sy+4, 8, block_id(lname))
        for _ in range(40): w.process_light_updates(budget=999)
        c = w.chunks[(0,0)]
        lit = int(c.light[8, sy+4, 8])
        near = int(c.light[8, sy+4, 6])
        check(f"{lname} emits {exp} & spreads (got {lit}, 2-away {near})",
              lit==exp and near==exp-2)
        w.set_block(8, sy+4, 8, 0)
        for _ in range(40): w.process_light_updates(budget=999)
        check(f"{lname} removed -> dark", int(c.light.max())==0)

    # baked into mesh
    w.set_block(8, sy+4, 8, block_id("glowstone"))
    for _ in range(40): w.process_light_updates(budget=999)
    from engine.mesh_builder import build_chunk_mesh
    s,_t = build_chunk_mesh(w, w.chunks[(0,0)])
    check("light baked into mesh verts (max~1.0)", float(s[:,6].max()) > 0.9)
    w.set_block(8, sy+4, 8, 0)
    for _ in range(40): w.process_light_updates(budget=999)

    # gravel falls like sand (gravity block via new addition)
    gx, gz = 5, 5; gy = w.surface_y(gx, gz)
    w.set_block(gx, gy+5, gz, block_id("gravel"))
    step(w, 3.0)
    check("gravel fell & re-placed",
          w.get_block(gx, gy+1, gz)==block_id("gravel") and w.get_block(gx,gy+5,gz)==0)

    # ---------- combat: attack a pig, it takes damage & is knocked back ----------
    px, pz = 10, 10; py = w.surface_y(px, pz)
    pig = Pig((px+0.5, py+1.05, pz+0.5)); pig.state_timer=999
    w.entities.append(pig)
    hp0 = pig.health
    origin = (px+0.5 - 2.0, py+1.6, pz+0.5)         # 2m to the -x side
    direction = (1.0, 0.0, 0.0)
    hit = w.attack(None, 4.0, origin, direction, 6.0)
    check("attack ray hit the pig", hit is pig)
    check("pig lost health", pig.health == hp0 - 4.0)
    check("pig hurt flash set", pig.hurt_timer > 0)
    vx_after = pig.vel[0]
    check("pig knocked back (+x, away from attacker)", vx_after > 0.5)

    # kill a slime -> it splits into two smaller slimes
    sx2, sz2 = 12, 12; syy = w.surface_y(sx2, sz2)
    big = Slime((sx2+0.5, syy+1.05, sz2+0.5), size=1.0); big.state_timer=999
    w.entities.append(big)
    before = len([e for e in w.entities if e.TYPE_NAME=="slime"])
    big.hurt(999, source_pos=(sx2+0.5, syy+1.6, sz2-2))
    step(w, 0.1)
    after = [e for e in w.entities if e.TYPE_NAME=="slime"]
    check(f"slime split on death ({before} -> {len(after)})",
          len(after)==2 and all(s.size < 1.0 for s in after))

    # ---------- sprint ----------
    # flat stone platform so terrain can't stall the run; pos pinned each frame
    bx0, bz0 = 8, 8; gy0 = w.surface_y(bx0, bz0)
    for ix in range(bx0-2, bx0+3):
        for iz in range(bz0-2, bz0+3):
            w.set_block(ix, gy0, iz, block_id("stone"))
    pl = Player(w.spawn_pos); w.player = pl
    home = (bx0+0.5, gy0+1.02, bz0+0.5)
    def run_speed(sprint):
        pl.pos[:] = home; pl.vel[:] = 0; pl.sprinting = sprint
        pl.move_z = 1.0; pl.move_x = 0.0
        for _ in range(40):
            pl.update(w, 1/60); pl.pos[:] = home    # pin position, keep velocity
        return math.hypot(pl.vel[0], pl.vel[2])
    walk_speed = run_speed(False)
    sprint_speed = run_speed(True)
    check(f"sprint faster than walk ({sprint_speed:.2f} > {walk_speed:.2f})",
          sprint_speed > walk_speed * 1.3)

    # ---------- flight: toggle, rise without gravity, descend ----------
    pl.sprinting=False; pl.move_z=0.0; pl.vel[:]=0
    pl.toggle_fly(); check("flight toggled on", pl.flying)
    y0 = pl.pos[1]; pl.fly_up=True; pl.fly_down=False
    for _ in range(30): pl.update(w, 1/60)
    check(f"fly ascends ({pl.pos[1]:.1f} > {y0:.1f})", pl.pos[1] > y0 + 0.5)
    yA = pl.pos[1]; pl.fly_up=False; pl.fly_down=True
    for _ in range(30): pl.update(w, 1/60)
    check(f"fly descends ({pl.pos[1]:.1f} < {yA:.1f})", pl.pos[1] < yA - 0.5)
    pl.fly_up=False; pl.fly_down=False
    yh = pl.pos[1]
    for _ in range(30): pl.update(w, 1/60)
    check("fly hovers (no gravity when idle)", abs(pl.pos[1]-yh) < 0.1)

    print(f"\nAll {P} feature checks passed.")

if __name__ == "__main__":
    main()
