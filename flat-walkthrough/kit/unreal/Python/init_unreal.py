# Runs automatically when the editor starts. Only acts when FLAT_RUN points at a script (automation runs).
import os
_script = os.environ.get("FLAT_RUN")
if _script and os.path.exists(_script):
    import unreal

    _state = {"n": 0}

    def _deferred(dt):
        _state["n"] += 1
        if _state["n"] == 60:            # let the editor finish loading first
            unreal.unregister_slate_post_tick_callback(_h)
            exec(compile(open(_script).read(), _script, "exec"), {"__file__": _script, "__name__": "__flat__"})

    _h = unreal.register_slate_post_tick_callback(_deferred)
