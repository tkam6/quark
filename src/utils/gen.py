import dataclasses as dcs
import os
import re
import sys
import typing as ty

from src.parser import internals as pint
from src.utils import consts as uconst

if ty.TYPE_CHECKING:
    from src.intrpr import cmd_reslvr as icrsr
    from src.intrpr import eng as ieng
    from src.intrpr import internals as iint


#########################
### CUSTOM EXCEPTIONS ###
#########################

class KeyboardInterruptWPrevileges(Exception):
    def __init__(self, e: Exception, child_pid: int) -> None:
        self.err = err
        self.child_pid = child_pid


class InvVarTypErr(Exception):
    def __init__(
        self,
        var_nm: str,
        var_typ: type,
        got_typ: type,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.var_nm = var_nm
        self.var_typ = var_typ
        self.got_typ = got_typ


class InvVarNmErr(Exception):
    def __init__(self, var_nm: str | None = None, msg: str | None = None) -> None:
        super().__init__(msg)
        self.msg = msg
        self.var_nm = var_nm

    def __str__(self) -> str:
        nm = "?" if self.var_nm is None else self.var_nm
        return (
            (super().__repr__() + ": ") if self.msg is not None else ""
            + f"name = {nm}"
        )


class InvVarValErr(Exception):
    def __init__(
        self,
        var_nm: str | None = None,
        var_val: ty.Any = None,
        msg: str | None = None,
    ) -> None:
        super().__init__(msg)
        self.msg = msg
        self.var_nm = var_nm
        self.var_val = var_val

    def __str__(self) -> str:
        nm = "?" if self.var_nm is None else self.var_nm
        val = "?" if self.var_val is None else self.var_val
        return (
            (super().__repr__() + ": ") if self.msg is not None else ""
            + (f"name = {nm}, value = {val}")
        )


class UnkVarErr(Exception):
    def __init__(self, var_nm: str | None = None, msg: str | None = None):
        super().__init__(msg)
        self.msg = msg
        self.var_nm = var_nm

    def __str__(self) -> str:
        nm = "?" if self.var_nm is None else self.var_nm
        return (
            (super().__repr__() + ": ") if self.msg is not None else ""
            + f"name = {nm}"
        )


class HowDidWeGetHere(Exception):
    pass


class EnvTblShmBufNone(Exception):
    pass


class EnvTblShmNone(Exception):
    pass


class EnvTblEmpty(Exception):
    pass


class EnvKeyTooLarge(Exception):
    def __init__(self, msg: str, offending_key: str) -> None:
        super().__init__(msg)
        self.offending_key = offending_key

class EnvValTooLarge(Exception):
    def __init__(self, msg: str, offending_val: str) -> None:
        super().__init__(msg)
        self.offending_val = offending_val

class EnvCntOutOfRng(Exception):
    pass

class InvAccess(Exception):
    pass


class CmdData(ty.NamedTuple):
    cmd_nm: str
    sub_cmd: str | None
    args: tuple[str, ...]
    opts: dict[str, str]
    flags: tuple[str, ...]
    cmd_reslvr: "icrsr.CmdReslvr"
    intrpr_vars: "iint.IntrprTbl"
    env_vars: "iint.EnvTbl"
    ext_cached_cmds: "dict[str, iint.CmdCacheEntry]"
    term_sz: os.terminal_size | None
    is_tty: bool
    stdin: str | None
    exec_fn: "ty.Callable[[ieng.Intrpr, str], int]"

class CmdSpec(ty.NamedTuple):
    min_args: int
    max_args: int | float
    opts: tuple[str, ...]
    flags: tuple[str, ...]
    parse_sub_cmds: bool = False
    sub_cmds: dict[str | None, tuple[int, int | float]] = dcs.field(default_factory=dict)


class HelpObj(ty.NamedTuple):
    usage: str
    summary: str
    details: tuple[str | tuple[str, ...], ...]


class WrapGeneratorToStealReturn:
    def __init__(self, gen: ty.Generator[ty.Any, ty.Any, ty.Any]) -> None:
        self.gen = gen
        self.val = None

    def __iter__(self) -> ty.Generator[ty.Any, ty.Any, ty.Any]:
        self.val = yield from self.gen
        return self.val


class StyleObj:
    """
    Style object to apply formatting to text objects.
    """
    reset = "\x1b[0m"
    bold = "\x1b[1m"

    red_4 = "\x1b[31m"
    green_4 = "\x1b[32m"
    yellow_4 = "\x1b[33m"
    blue_4 = "\x1b[34m"
    magenta_4 = "\x1b[35m"
    cyan_4 = "\x1b[36m"

    green_bg_8 = "\x1b[48;5;22m"
    magenta_bg_8 = "\x1b[48;5;55m"
    white_bg_8 = "\x1b[48;5;248m"
    black_fg_8 = "\x1b[38;5;0m"

    def fmt(self, string: str, apply_fmting: bool, *args: str) -> str:
        return (
            ("".join(args) + string + self.reset) if apply_fmting else string
        )


def ljust(string: str, amt: int) -> str:
    return string.ljust(amt + len(string) - len(rm_ansi("", string)))


def rjust(string: str, amt: int) -> str:
    return string.rjust(amt + len(string) - len(rm_ansi("", string)))


def esc_chrs_all(s: str, extra: tuple[str, ...] = ()) -> str:
    to_ret = []
    for ch in s:
        if ch in pint.REV_ESC_CHR_MAP:
            to_ret.append(pint.REV_ESC_CHR_MAP[ch])
            continue
        if ch in extra:
            to_ret.append("\\" + ch)
            continue
        to_ret.append(ch)
    return "".join(to_ret)


def esc_chrs(s: str, to_esc: tuple[str]) -> str:
    to_ret = []
    for ch in s:
        if ch in to_esc:
            to_ret.append("\\" + ch)
            continue
        to_ret.append(ch)
    return "".join(to_ret)


def condense_pth(pth: str) -> str:
    return re.sub(usr_dir_regex, "~", pth)


def set_lgrs(lgrs) -> None:
    global _lgrs
    _lgrs = lgrs


def write(s: str, flush: bool = True) -> None:
    sys.stdout.write(s)
    sys.stdout.flush() if flush else None


def fatal(
    msg: str,
    ret: int,
    exc_txt: str | None = None,
    nm: str | None = None
) -> ty.NoReturn:
    src = f"{nm}: " if nm is not None else ""
    fl_log_txt = rm_ansi(
        "",
        (src + msg) if exc_txt is None else (src + exc_txt),
    )
    _lgrs.lgr_c.fatal(src + msg)
    _lgrs.fl_lgr.fatal(fl_log_txt)
    sys.exit(ret)


def fatal_Q(
    msg: str,
    ret: int,
    exc_txt: str | None = None,
    nm: str | None = None
) -> ty.NoReturn:
    src = f"{nm}: " if nm is not None else ""
    fl_log_txt = rm_ansi(
        "",
        (src + msg) if exc_txt is None else (src + exc_txt)
    )
    if _lgrs is not None:
        _lgrs.lgr_q.fatal(src + msg)
        _lgrs.fl_lgr.fatal(fl_log_txt)
    else:
        sys.stderr.write(
            f"{uconst.ANSI_BOLD_RED_4}FQ:{uconst.ANSI_RESET} {src}{msg}\n"
        )
        sys.stderr.flush()
    sys.exit(ret)


def crit(msg: str, exc_txt: str | None = None, nm: str | None = None) -> None:
    src = f"{nm}: " if nm is not None else ""
    fl_log_txt = rm_ansi(
        "",
        (src + msg) if exc_txt is None else (src + exc_txt),
    )
    _lgrs.lgr_c.crit(src + msg)
    _lgrs.fl_lgr.crit(fl_log_txt)


def crit_Q(
    msg: str,
    exc_txt: str | None = None,
    nm: str | None = None
) -> None:
    src = f"{nm}: " if nm is not None else ""
    fl_log_txt = rm_ansi(
        "",
        (src + msg) if exc_txt is None else (src + exc_txt),
    )
    if _lgrs is not None:
        _lgrs.lgr_q.crit(src + msg)
        _lgrs.fl_lgr.crit(fl_log_txt)
    else:
        sys.stderr.write(
            f"{uconst.ANSI_BOLD_RED_4}CQ:{uconst.ANSI_RESET} {src}{msg}\n"
        )
        sys.stderr.flush()


def err(msg: str, nm: str | None = None) -> None:
    src = f"{nm}: " if nm is not None else ""
    _lgrs.lgr_c.err(src + msg)
    _lgrs.fl_lgr.err(src + msg)


def err_Q(msg: str, nm: str | None = None) -> None:
    src = f"{nm}: " if nm is not None else ""
    if _lgrs is not None:
        _lgrs.lgr_q.err(src + msg)
        _lgrs.fl_lgr.err(src + msg)
    else:
        sys.stderr.write(
            f"{uconst.ANSI_BOLD_RED_4}EQ:{uconst.ANSI_RESET} {src}{msg}\n"
        )
        sys.stderr.flush()


def warn(msg: str, nm: str | None = None) -> None:
    src = f"{nm}: " if nm is not None else ""
    _lgrs.lgr_c.warn(src + msg)
    _lgrs.fl_lgr.warn(src + msg)


def warn_Q(msg: str, nm: str | None = None) -> None:
    src = f"{nm}: " if nm is not None else ""
    if _lgrs is not None:
        _lgrs.lgr_q.warn(src + msg)
        _lgrs.fl_lgr.warn(src + msg)
    else:
        sys.stderr.write(
            f"{uconst.ANSI_BOLD_YELLOW_4}WQ:{uconst.ANSI_RESET} {src}{msg}"
        )
        sys.stderr.flush()


def info(msg: str, nm: str | None = None) -> None:
    src = f"{nm}: " if nm is not None else ""
    _lgrs.lgr_c.info(src + msg)
    _lgrs.fl_lgr.info(src + msg)


def info_Q(msg: str, nm: str | None = None) -> None:
    src = f"{nm}: " if nm is not None else ""
    if _lgrs is not None:
        _lgrs.lgr_q.info(src + msg)
        _lgrs.fl_lgr.info(src + msg)
    else:
        sys.stderr.write(
            f"{uconst.ANSI_BOLD}IQ:{uconst.ANSI_RESET} {src}{msg}\n",
        )
        sys.stderr.flush()


def debug(msg: str, nm: str | None = None) -> None:
    src = f"{nm}: " if nm is not None else ""
    _lgrs.lgr_c.debug(src + msg)
    _lgrs.fl_lgr.debug(src + msg)


def debug_Q(msg: str, nm: str | None = None) -> None:
    src = f"{nm}: " if nm is not None else ""
    if _lgrs is not None:
        _lgrs.lgr_q.debug(src + msg)
        _lgrs.fl_lgr.debug(src + msg)
    else:
        sys.stderr.write(
            f"{uconst.ANSI_BOLD}DQ:{uconst.ANSI_RESET} {src}{msg}\n",
        )
        sys.stderr.flush()


def fmt_d_stmt(
    src: str,
    lhs: str,
    rhs: str | None = None,
    pad: int = 24,
    lhs_rhs_sep: str = " -> ",
) -> str:
    full_str = f"[{src}] {lhs}".ljust(pad)
    if rhs:
        full_str += f"{lhs_rhs_sep}{rhs}"
    return full_str


def fmt_t_ns(time_expo: int, ns: int) -> str:
    unit = "?"
    if time_expo == 6:
        unit = "ms"
    elif time_expo == 3:
        unit = "us"
    elif time_expo == 0:
        unit = "ns"
    elif time_expo == 9:
        unit = "s"
    return str(round(ns / 10 ** time_expo, 3)) + unit


_lgrs = None
S = StyleObj()
ESC_CHR_MAP = pint.ESC_CHR_MAP
usr_dir_regex = re.compile(rf"^{os.path.expanduser("~")}")
rm_ansi = re.compile(r"""\x1b\[[;\d]*[A-Za-z]""", re.VERBOSE).sub
