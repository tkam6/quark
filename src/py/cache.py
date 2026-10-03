# Don't forget to convert the Unix timestamps to human datetime format
import os
import re
import typing as ty

from src.utils import err_codes as uerr
from src.utils import gen as ugen

CMD_NM = __name__.split(".")[-1]

HELP = ugen.HelpObj(
    usage=f"{CMD_NM} [flag ...] [cmd ...]",
    summary="Display cached command information",
    details=(
        "ARGUMENTS",
        ("cmd", "Command to fetch cache info about"),
        "OPTIONS",
        ("none", ""),
        "FLAGS",
        ("-t, --mtime", "Display modify time of module file"),
        ("-p, --path", "Display path of module file")
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=0,
    max_args=float("inf"),
    opts=(),
    flags=(
        "-t", "--mtime",
        "-p", "--path"
    )
)


class Out(ty.NamedTuple):
    nm: str
    sz: str | None
    mtime: str | None
    pth: str | None


class Err(ty.NamedTuple):
    nm: str
    msg: str


def run(data: ugen.CmdData) -> int:
    to_write: list[Out | Err]

    err_code = uerr.ERR_ALL_GOOD
    mtimes = "-t" in data.flags or "--mtime" in data.flags
    pths = "-p" in data.flags or "--path" in data.flags
    nm_max_len = 0
    sz_max_len = 0
    mtime_max_len = 0
    pth_max_len = 0
    to_write = []

    if not data.args:
        for i in data.ext_cached_cmds.values():
            nm_max_len = max(nm_max_len, len(i.cmd))
            sz_max_len = max(sz_max_len, len(str(i.sz)))
            mtime_max_len = max(mtime_max_len, len(str(i.mtime)))
            pth_max_len = max(pth_max_len, len(i.mod.__file__))
            to_write.append(Out(
                nm=i.cmd,
                sz=i.sz,
                mtime=(i.mtime if mtimes else None),
                pth=(i.mod.__file__ if pths else None)
            ))

    else:
        for arg in data.args:
            if arg not in data.ext_cached_cmds:
                to_write.append(Err(
                    nm=arg,
                    msg="No such cached command"
                ))
                continue
            entry = data.ext_cached_cmds[arg]
            nm_max_len = max(nm_max_len, len(entry.cmd))
            sz_max_len = max(sz_max_len, len(str(entry.sz)))
            mtime_max_len = max(mtime_max_len, len(str(entry.mtime)))
            pth_max_len = max(pth_max_len, len(entry.mod.__file__))
            to_write.append(Out(
                nm=entry.cmd,
                sz=entry.sz,
                mtime=(entry.mtime if mtimes else None),
                pth=(entry.mod.__file__ if pths else None)
            ))

    usr_dir = os.path.expanduser("~")
    usr_dir_patt = re.compile(f"^{usr_dir}")
    # For quotes surrounding it in output
    nm_max_len += 2
    for j in to_write:
        if isinstance(j, Err):
            ugen.err(f"{j.msg}: '{j.nm}'", nm=data.cmd_nm)
        elif isinstance(j, Out):
            fmtd_nm = "'" + ugen.S.fmt(j.nm, data.is_tty, ugen.S.green_4) + "'"
            if mtimes or pths:
                fmtd_nm = ugen.ljust(fmtd_nm, nm_max_len)
            ugen.write(
                ugen.rjust(str(j.sz), sz_max_len)
                + " " + fmtd_nm
                + (f" [{j.mtime}]" if mtimes else "")
                + (f" ({re.sub(usr_dir_patt, '~', j.pth)})" if pths else "")
                + "\n"
            )
    return err_code
