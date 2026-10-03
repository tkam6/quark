import os

from src.utils import err_codes as uerr
from src.utils import gen as ugen

CMD_NM = __name__.split(".")[-1]

HELP = ugen.HelpObj(
    usage=f"{CMD_NM} [flag] dir [...]",
    summary="Make directories",
    details=(
        "ARGUMENTS",
        ("dir", "Directory to create"),
        "OPTIONS",
        ("none", ""),
        "FLAGS",
        ("-o, --exist-ok", "If directory already exists, don't make a fuss"),
        ("-p, --make-parents", "Make parent directories")
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=1,
    max_args=float("inf"),
    opts=(),
    flags=(
        "-o", "--exist-ok",
        "-p", "--make-parents",
    )
)

ERR_NO_PARENT = 1000


def run(data: ugen.CmdData) -> int:
    err_code = uerr.ERR_ALL_GOOD
    exist_ok = "-o" in data.flags or "--exist-ok" in data.flags
    mk_parents = "-p" in data.flags or "--make-parents" in data.flags
    mk_fn = os.makedirs if mk_parents else os.mkdir

    for arg in data.args:
        try:
            mk_fn(arg)
        except FileExistsError:
            if not exist_ok:
                err_code = err_code or uerr.ERR_FL_DIR_EXISTS
                ugen.err(f"Already exists: \"{arg}\"", nm=data.cmd_nm)
        except FileNotFoundError:
            err_code = err_code or ERR_NO_PARENT
            ugen.err(f"No parent: \"{arg}\"", nm=data.cmd_nm)
        except PermissionError:
            err_code = err_code or uerr.ERR_PERM_DENIED
            ugen.err(f"Access denied: cannot create \"{arg}\"", nm=data.cmd_nm)
        except OSError as e:
            err_code = err_code or uerr.ERR_OS_ERR
            ugen.err(f"OS error; {e.strerror}", nm=data.cmd_nm)

    return err_code
