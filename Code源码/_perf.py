import time, numpy as np, traceback, sys
try:
    import content.blocks, content.items
    from world.world import World
    from content.registry import block_id
    w=World(4242); w.ensure_chunks_around(8,8)
    t=time.time()
    while w._pending and time.time()-t<15:
        w.process_gen_results(budget=200); time.sleep(0.005)
    sy=w.surface_y(8,8); c=w.chunks[(0,0)]
    print("setup chunks", len(w.chunks))
    w.light_dirty.clear()
    w.set_block(8, sy+1, 8, block_id("stone"))
    print("dark place dirty:", len(w.light_dirty))
    w.set_block(8, sy+3, 8, block_id("glowstone"))
    print("glow dirty chunks:", len(w.light_dirty))
    t0=time.perf_counter()
    while w.light_dirty: w.process_light_updates(budget=99)
    print("relight ms:", round((time.perf_counter()-t0)*1000,2), "lit", int(c.light[8,sy+3,8]), "2away", int(c.light[8,sy+3,6]))
    from world import lighting
    t0=time.perf_counter()
    for _ in range(20): lighting.relight_chunk(w,c)
    print("relight_chunk avg ms:", round((time.perf_counter()-t0)/20*1000,2))
    import settings
    t0=time.perf_counter(); w.explode(8.5, sy+2.5, 8.5, 9.0, 4.5)
    print("explode ms:", round((time.perf_counter()-t0)*1000,2), "debris", w.debris.count, "dirty", len(w.light_dirty))
    print("PERF_OK")
except Exception:
    traceback.print_exc(); sys.exit(2)
