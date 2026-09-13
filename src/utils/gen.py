import atexit
import os
import re
import select
import signal as sig
import sys
import termios
import tty
import typing as ty

from src.parser import internals as pint
from src.utils import consts as uconst
from src.logger import eng as leng
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
    def __init__(self, var_nm: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.var_nm = var_nm


class InvVarValErr(Exception):
    def __init__(
        self,
        message: str = "",
        var_nm: str | None = None,
        var_val: ty.Any = None,
        *args: ty.Any,
        **kwargs: ty.Any
    ):
        super().__init__(*args, **kwargs)
        self.var_nm = var_nm
        self.var_val = var_val

    def __str__(self) -> str:
        msg = super().__str__()
        if self.var_nm is None and self.var_val is None:
            return msg
        if self.var_nm is None:
            if not msg:
                return f"Invalid variable value {self.var_val}"
            return f"{msg} (variable value {self.var_val})"
        elif self.var_val is None:
            if not msg:
                return f"Invalid variable value for {self.var_nm}"
            return f"{msg} (variable {self.var_nm})"
        else:
            if not msg:
                return f"Invalid variable value {self.var_val} for {self.var_nm}"
            return f"{msg} (variable {self.var_nm} with value {self.var_val})"


class UnkVarErr(Exception):
    def __init__(self, message: str = "", *, var_nm: str | None = None):
        self.var_nm = var_nm

    def __str__(self) -> str:
        msg = super().__str__()
        if self.var_nm is None:
            return msg
        if msg:
            return f"{msg} (with var {self.var_nm})"
        return f"Unknown variable: {self.var_nm}"

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
    exec_fn: "ty.Callable[[ieng.Intrpr, str], int | ty.NoReturn]"

class CmdSpec(ty.NamedTuple):
    min_args: int
    max_args: int | float
    opts: tuple[str, ...]
    flags: tuple[str, ...]
    parse_sub_cmds: bool = False
    sub_cmds: dict[str | None, tuple[int, int | float]] = {}

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
        (src + msg) if exc_txt is None else (src + exc_txt)
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
    # To output to STDERR before initialisation of loggers
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
        (src + msg) if exc_txt is None else (src + exc_txt)
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
        (src + msg) if exc_txt is None else (src + exc_txt)
    )
    # To output to STDERR before initialisation of loggers
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
    # To output to STDERR before initialisation of loggers
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
    # To output to STDERR before initialisation of loggers
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
    # To output to STDERR before initialisation of loggers
    if _lgrs is not None:
        _lgrs.lgr_q.info(src + msg)
        _lgrs.fl_lgr.info(src + msg)
    else:
        sys.stderr.write(
            f"{uconst.ANSI_BOLD}IQ:{uconst.ANSI_RESET} {src}{msg}\n"
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
            f"{uconst.ANSI_BOLD}DQ:{uconst.ANSI_RESET} {src}{msg}\n"
        )
        sys.stderr.flush()


def fmt_d_stmt(
    src: str,
    lhs: str,
    rhs: str | None = None,
    pad: int = 24,
    lhs_rhs_sep: str = " -> "
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


# Source - https://stackoverflow.com/a/46675451
# Posted by netzego, modified by community. See post 'Timeline' for change history
# Retrieved 2026-04-01, License - CC BY-SA 3.0
def get_pos() -> tuple[int, int] | None:
    buf = ""
    stdin = sys.stdin.fileno()
    tattr = termios.tcgetattr(stdin)

    try:
        tty.setcbreak(stdin, termios.TCSANOW)
        sys.stdout.write("\x1b[6n")
        sys.stdout.flush()
        while True:
            buf += sys.stdin.read(1)
            if buf[-1] == "R":
                break
    finally:
        termios.tcsetattr(stdin, termios.TCSANOW, tattr)

    # Reading the actual values, but what if a keystroke appears while reading
    # from stdin? As dirty work around, getpos() returns if this fails: None
    matches = re.match(get_pos_regex, buf)
    if matches is None:
        return None
    groups = matches.groups()

    return (int(groups[0]), int(groups[1]))


#############
### INPUT ###
#############
# Source - https://stackoverflow.com/a/17939632
# Posted by Vitja Makarov
# Retrieved 2026-06-28, License - CC BY-SA 3.0
def setup_term(fd, when=termios.TCSAFLUSH):
    mode = termios.tcgetattr(fd)
    mode[tty.LFLAG] = mode[tty.LFLAG] & ~(termios.ECHO | termios.ICANON)
    termios.tcsetattr(fd, when, mode)


def getch(timeout: float | None = None) -> str | None:
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        setup_term(fd)
        try:
            rw, wl, xl = select.select([fd], [], [], timeout)
        except select.error:
            return None
        if rw:
            return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return None


class InpHdlr:
    def __init__(self) -> None:
        self.fd = sys.stdin.fileno()
        self.old_sett = termios.tcgetattr(self.fd)
        atexit.register(self.reset_sett)

    def set_new_sett(self):
        tty.setraw(self.fd)

    def reset_sett(self) -> None:
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_sett)

    def kbhit(self, timeout=0):
        r, _, _ = select.select([self.fd], [], [], timeout)
        return bool(r)

    def getch(self) -> str:
        return os.read(self.fd, 1).decode()


def inp(inp_hdlr: InpHdlr, hist: str, tab_spaces: int = 4) -> str:
    buf: list[str]

    init_pos = get_pos()
    while init_pos is None:
        init_pos = get_pos()
    init_ln, init_col = init_pos
    cur_ln, cur_col = init_ln, init_col
    prev_ch = None
    ch = None
    buf = []
    # TODO: Make it include current line being typed in history, i.e. you get
    # last entry in history to be the current line being typed. Tried to
    # implement, but it wouldn't work
    # hist.append("")
    hist_len = len(hist)
    hist_pos = hist_len
    inp_hdlr.set_new_sett()

    while True:
        ins_ch = False
        full_key = inp_hdlr.getch()
        while inp_hdlr.kbhit():
            full_key += inp_hdlr.getch()

        # For tab completion
        # write(mv_cur(cur_ln + 1, 0))
        # write("\x1b[0J")
        # write(mv_cur(cur_ln, cur_col))

        # ^a - move to start of line
        if full_key == "\x01":
            cur_col = init_col

        # ^b or left - move one character back
        elif full_key in ("\x02", "\x1b[D"):
            cur_col -= 1 if cur_col > init_col else 0

        # ^c - interrupt
        elif full_key == "\x03":
            raise KeyboardInterrupt

        # ^d - EOF or kill character under cursor
        elif full_key in ("\x04", "\x1b[3~"):
            # EOF only if ^d
            if not buf and full_key != "\x1b[3~":
                raise EOFError
            # Kill character under cursor
            if cur_col < init_col + len(buf):
                buf.pop(cur_col - init_col)

        # ^e - move to end of line
        elif full_key == "\x05":
            cur_col = init_col + len(buf)

        # ^f or right - move one character forward
        elif full_key in ("\x06", "\x1b[C"):
            cur_col += 1 if cur_col < init_col + len(buf) else 0

        # ^p or up - previous match from history
        elif full_key in ("\x10", "\x1b[A"):
            if hist and hist_pos > 0:
                hist_pos -= 1
                buf = list(hist[hist_pos])
                cur_col = init_col + len(buf)

        # ^n or down - next match from history
        elif full_key in ("\x0e", "\x1b[B"):
            if hist and hist_pos < hist_len - 1:
                hist_pos += 1
                buf = list(hist[hist_pos])
                cur_col = init_col + len(buf)

        # ^u - clear line
        elif full_key == "\x15":
            buf.clear()
            cur_col = init_col

        # ^w - kill word before cursor
        elif full_key == "\x17":
            buf_len = len(buf)
            # Delete whitespace just before cursor before deleting word
            while (
                cur_col - init_col > 0
                and buf[cur_col - init_col - 1].isspace()
            ):
                cur_col -= 1
                buf.pop(cur_col - init_col)
            # Delete the actual word (i.e. till we hit whitespace again)
            while (
                cur_col - init_col > 0
                and not buf[cur_col - init_col - 1].isspace()
            ):
                cur_col -= 1
                buf.pop(cur_col - init_col)

        elif full_key == "\x0c":
            write("Work in progress")

        # alt+b or ^left - move one word backward
        # No buffer modification. While the start of the buffer is not reached
        # (which happens when current column is same as initial column) and
        # character before the cursor is to be jumped (trailing whitespace or
        # actual word character), then move the cursor one character back
        elif full_key in ("\x1bb", "\x1b[1;5D"):
            # Whitespace before cursor and after previous word
            while cur_col > init_col and buf[cur_col - init_col - 1].isspace():
                cur_col -= 1
            # Actual word
            while (
                cur_col > init_col
                and not buf[cur_col - init_col - 1].isspace()
            ):
                cur_col -= 1

        # alt+d or ^del - kill word forward
        # Current column does not change; current index in the buffer is
        # calculated, and while it's less than length of the buffer (ensure
        # delete range does not go beyond buffer) pop character under cursor
        # (i.e. character at current index)
        elif full_key in ("\x1bd", "\x1b[3;5~"):
            curr_idx = cur_col - init_col
            # Kill whitespace after cursor and before next word
            while curr_idx < len(buf) and buf[cur_col - init_col].isspace():
                buf.pop(cur_col - init_col)
            # Kill actual word forward
            while (
                curr_idx < len(buf)
                and not buf[cur_col - init_col].isspace()
            ):
                buf.pop(cur_col - init_col)

        # alt+f or ^right - move one word forward
        elif full_key in ("\x1bf", "\x1b[1;5C"):
            # Whitespace after cursor and before next word
            while (
                cur_col < init_col + len(buf)
                and buf[cur_col - init_col].isspace()
            ):
                cur_col += 1
            # The actual word
            while (
                cur_col < init_col + len(buf)
                and not buf[cur_col - init_col].isspace()
            ):
                cur_col += 1

        # Backspace (kill char before cursor)
        elif full_key == "\x7f":
            if buf and cur_col > init_col:
                cur_col -= 1
                buf.pop(cur_col - init_col)

        # Tab
        elif full_key == "\t":
            for i in range(tab_spaces):
                buf.insert(cur_col - init_col, " ")
                cur_col += 1
        # Tab (completion)
        # elif full_key == "\t":
        #     mv_cur(cur_ln + 1, 0)
        #     items = os.listdir(".")
        #     write(f"\n{mv_cur_col(0)}".join(items))
        #     mv_cur(cur_ln, cur_col)

        # Return
        elif full_key in ("\r", "\n"):
            write(mv_cur_col(0) + "\n", flush=True)
            break

        # ^z - send SIGSTOP to self
        elif full_key == "\x1a":
            inp_hdlr.reset_sett()
            os.kill(os.getpid(), sig.SIGSTOP)
            cur_pos = get_pos()
            while cur_pos is None:
                cur_pos = get_pos()
            cur_ln, cur_col = cur_pos

        # Ununsed
        elif full_key in (
            "\x00", "\x1c", "\x1d", "\x1e", "\x1f", "\x7f",        # Number row
            "\x11", "\x12", "\x14", "\x19", "\x0f", "\x1c",        # Top row
            "\x13", "\x07", "\x08", "\n", "\x0b",                  # Middle row
            "\x18", "\x16", "\x02", "\x0e", "\r", "\x1f",          # Bottom row
        ):
            pass

        else:
            ins_ch = True

        if ins_ch:
            buf.insert(cur_col - init_col, full_key)
            cur_col += 1
        # cols = os.get_terminal_size().columns
        # for i, sli in enumerate(buf[:: cols - init_cols]):
        #     if i 
        write(mv_cur(cur_ln, init_col) + str_join(buf).expandtabs(4))
        write(uconst.ANSI_ERASE_CUR_TO_EOL)
        write(mv_cur_col(cur_col))

    return str_join(buf)


####################
### GLOBAL SCOPE ###
####################
rm_ansi = re.compile(r"""\x1b\[[;\d]*[A-Za-z]""", re.VERBOSE).sub
_lgrs = None
S = StyleObj()
# For inp()
get_pos_regex = re.compile(r"^\x1b\[(\d*);(\d*)R")
usr_dir_regex = re.compile(rf"^{os.path.expanduser("~")}")
str_join = "".join
mv_cur = lambda ln, col: f"\x1b[{ln};{col}H"
mv_cur_col = lambda col: f"\x1b[{col}G"
ESC_CHR_MAP = pint.ESC_CHR_MAP
