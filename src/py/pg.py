# TODO: Need to not load whole file into memory
import os

from src.utils import err_codes as uerr
from src.utils import gen as ugen

CMD_NM = __name__.split(".")[-1]

HELP = ugen.HelpObj(
    usage=CMD_NM,
    summary="Page text",
    details=(
        "ARGUMENTS",
        ("none", ""),
        "OPTIONS",
        ("none", ""),
        "FLAGS",
        ("none", "")
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=0,
    max_args=float("inf"),
    opts=(),
    flags=()
)

ERR_MSG_MAP = {
    uerr.ERR_FL_404     : "No such file",
    uerr.ERR_PERM_DENIED: "Access denied",
    uerr.ERR_IS_A_DIR   : "Is a directory",
    uerr.ERR_OS_ERR     : "OS error",
    uerr.ERR_DECODE_ERR : "Cannot decode file"
}


def pg(txt: str, src: str | None, term_sz: os.terminal_size, is_tty: bool) -> None:
    # str.splitlines was not intentionally used: it doesn't count newline at
    # end of string
    txt_split = txt.split("\n")
    # TODO: Make filename line sticky, meaning make it remain on screen even
    # after scrolling, you dirty-minded dog
    txt_split.insert(0, ugen.S.fmt(("- / STDIN" if src is None else src), is_tty, ugen.S.green_4))
    txt_split_fit = []
    for i in txt_split:
        # That 1 added is for if line (i) is empty. If could also be done like
        # this: `if not i: txt_split_fit.append(i)` before the following the
        # for loop, but this felt more concise, albeit more stupid
        for j in range(0, len(i) + 1, term_sz.columns):
            txt_split_fit.append(i[j : j + term_sz.columns])
    # I have no idea why we need to subtract 1 here
    # But I've implemented it as a temporary solution because top line gets
    # scrolled down
    initial_disp = txt_split_fit[: term_sz.lines - 1]
    txt_split_fit = txt_split_fit[term_sz.lines - 1 :]
    ugen.write("\n".join(initial_disp))
    try:
        # TODO: Convert this into a while loop to enable jumping up/down
        # screenfuls or half-screenfuls or similar functionality. And implement
        # said functionality
        for ln in txt_split_fit:
            ugen.write("\n" + ln)
            while True:
                key = ugen.getch()
                if ord(key) == 10:
                    break
    except KeyboardInterrupt:
        pass


def get_cntnt(pth: str) -> str | tuple[int, Exception]:
    try:
        with open(pth) as f:
            return f.read()
    except FileNotFoundError as e:
        return (uerr.ERR_FL_404, e)
    except PermissionError as e:
        return (uerr.ERR_PERM_DENIED, e)
    except IsADirectoryError as e:
        return (uerr.ERR_IS_A_DIR, e)
    except OSError as e:
        return (uerr.ERR_OS_ERR, e)
    except UnicodeDecodeError as e:
        return (uerr.ERR_DECODE_ERR, e)


def run(data: ugen.CmdData) -> int:
    err_code = uerr.ERR_ALL_GOOD
    txts = {}
    if data.stdin:
        txts[None] = data.stdin
    for arg in data.args:
        # TODO: Need to add in details in e.strerror in OSError cases
        ret = get_cntnt(arg)
        if not isinstance(ret, str):
            err_code = err_code or ret[0]
            ugen.err(ERR_MSG_MAP[ret[0]], nm=data.cmd_nm)
            continue
        txts[arg] = ret
    for src, txt in txts.items():
        pg(txt, src, data.term_sz, data.is_tty)
    return err_code
