import runpy as rp
import typing as ty

from src.utils import consts as uconst
from src.utils import gen as ugen

if ty.TYPE_CHECKING:
    from src.intrpr import internals as iint


class Cfg(ty.NamedTuple):
    prompt: "str | ty.Callable[[iint.IntrprTbl], str]"
    pth: tuple[str, ...]
    aliases: dict[str, str]
    ln_mode: str


def sandbox_runpy(fl: str) -> dict[str, ty.Any] | None:
    """
    Actually get the config from the configuration file.
    I don't know if this is actually sandboxing the load of the config file.
    Need to test. TODO!

    :param fl: Configuration filepath.
    :type fl: str

    :returns: Config module's globals dictionary.
    :rtype: dict[str, typing.Any] | None
    """
    try:
        return rp.run_path(fl)
    except FileNotFoundError:
        return None


def err_typ_repo(key: str, expd_typs: tuple[type, ...], got_typ: type) -> None:
    comma_sepd = ", ".join(f"'{i.__name__}'" for i in expd_typs[: -1])
    or_sepd = f"{' or ' if comma_sepd else ''}'{expd_typs[-1].__name__}'"
    expd_str = comma_sepd + or_sepd
    ugen.err_Q(
        f"(config) Expected {expd_str}, got '{got_typ.__name__}' for key '{key}'"
    )
    ugen.info_Q(f"(config) Using default value for '{key}'")


def get_cfg() -> Cfg:
    """
    TODO: Fill up!
    ???

    :returns: Config object containing values from the config file, if valid,
              else default values.
    :rtype: Cfg
    """
    aliases: dict[str, str]

    ln_mode = uconst.Defaults.LN_MODE
    prompt = uconst.Defaults.PROMPT
    pth = uconst.Defaults.PTH
    aliases = {}

    cfg = sandbox_runpy(uconst.CFG_FL)
    if cfg is None:
        return Cfg(ln_mode=ln_mode, prompt=prompt, pth=pth, aliases=aliases)

    for key in cfg:
        val = cfg[key]
        # To continue outer loop when checking iterable values
        valid_val = True

        # Callables and strings for prompt variable
        if key == "PROMPT":
            if not (isinstance(val, str) or callable(val)):
                err_typ_repo(key, expd_typs=(str, callable), got_typ=type(val))
                continue
            prompt = val

        # Tuple of strings for PATH variable
        elif key == "PTH":
            if not isinstance(val, tuple):
                err_typ_repo(key, expd_typs=(tuple,), got_typ=type(val))
                continue
            for i in val:
                if not isinstance(i, str):
                    ugen.err_Q("Expected 'str' values in value of '{key}'")
                    valid_val = False
                    break
            if not valid_val:
                continue
            pth = val

        # Dict of string: string pairs for aliases
        elif key == "ALIASES":
            if not isinstance(val, dict):
                err_typ_repo(key, expd_typs=(dict,), got_typ=type(val))
                continue
            for k, v in val.items():
                if not isinstance(k, str) or not isinstance(v, str):
                    ugen.err_Q(f"Expected 'str: str' values in value of {key}")
                    valid_val = False
                    break
            if not valid_val:
                continue
            aliases = val

        elif key == "LN_MODE":
            if not isinstance(val, str):
                err_typ_repo(key, expd_typs=(str,), got_typ=type(val))
                continue
            if val not in uconst.ValidVals.LN_MODE:
                ugen.err_Q(f"Invalid line mode: '{val}'")
                break
            ln_mode = val

    return Cfg(ln_mode=ln_mode, prompt=prompt, pth=pth, aliases=aliases)
