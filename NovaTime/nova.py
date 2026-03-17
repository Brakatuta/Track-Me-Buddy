import asyncio
from .novatime import NovaTime, NovaConfig

cfg: NovaConfig | None = None


def init_config(cfg_url, cfg_username, cfg_password,
                cfg_http_auth_username, cfg_http_auth_password, cfg_headless):
    global cfg
    cfg = NovaConfig(
        url                = cfg_url,
        username           = cfg_username,
        password           = cfg_password,
        http_auth_username = cfg_http_auth_username,
        http_auth_password = cfg_http_auth_password,
        headless           = cfg_headless,
        wait_ms            = 3000,
    )
    print(f"[Nova] Config initialised for user '{cfg_username}' @ {cfg_url}")


# ── Async action implementations ──────────────────────────────────────────────

async def arbeits_beginn():
    async with NovaTime(cfg) as nt:
        await nt.kommen()

async def arbeits_ende():
    async with NovaTime(cfg) as nt:
        await nt.gehen()

async def dienstgang_gehen():
    async with NovaTime(cfg) as nt:
        await nt.dg_gehen()

async def dienstgang_kommen():
    async with NovaTime(cfg) as nt:
        await nt.dg_kommen()

async def pause_start():
    async with NovaTime(cfg) as nt:
        await nt.pause_start()

async def pause_ende():
    async with NovaTime(cfg) as nt:
        await nt.pause_ende()

async def get_saldo():
    async with NovaTime(cfg) as nt:
        return await nt.info()


nova_funcs: dict[str, callable] = {
    "start_work":          arbeits_beginn,
    "end_work":            arbeits_ende,
    "start_business_trip": dienstgang_gehen,
    "end_business_trip":   dienstgang_kommen,
    "start_pause":         pause_start,
    "end_pause":           pause_ende,
    "saldo":               get_saldo,
    "test":                get_saldo,
}


def run_nova_action(action_type: str):
    """
    Run a NovaTime action synchronously.
    Raises RuntimeError if cfg is not initialised.
    Raises KeyError if action_type is unknown.
    Propagates any exception from the async action so callers can react.
    Returns the action's return value (e.g. the saldo string).
    """
    if cfg is None:
        raise RuntimeError("Nova config not initialised — call init_config() first.")

    action = nova_funcs.get(action_type)
    if action is None:
        raise KeyError(f"Action '{action_type}' not found. Available: {list(nova_funcs)}")

    return_data = asyncio.run(action())

    if isinstance(return_data, str):
        print(f"[Nova] {action_type} result: {return_data}")

    return return_data