import math

from src.utils import err_codes as uerr
from src.utils import gen as ugen

CMD_NM = __name__.split(".")[-1]

HELP = ugen.HelpObj(
    usage=f"{CMD_NM} fl [...]",
    summary="Run a script in forked child process",
    details=(
        "ARGUMENTS",
        ("file", "Script to run"),
        "OPTIONS",
        ("none", ""),
        "FLAGS",
        ("none", "")
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=1,
    max_args=math.inf,
    opts=(),
    flags=()
)

ERR_FROM_CMD = 1000


def run(data: ugen.CmdData) -> int:
    err_code = uerr.RC.ALL_GOOD

    for arg in data.args:
        try:
            with open(arg) as f:
                fl_cntnt = f.read()
        except FileNotFoundError:
            ugen.err(f"No such file/directory: \"{arg}\"", nm=data.cmd_nm)
            return uerr.RC.FL_404
        except PermissionError:
            ugen.err(f"Access denied: \"{arg}\"", nm=data.cmd_nm)
            return uerr.RC.PERM_DENIED
        except IsADirectoryError:
            ugen.err(f"Is a directory: \"{arg}\"", nm=data.cmd_nm)
            return uerr.RC.IS_A_DIR
        except UnicodeDecodeError:
            ugen.err("Cannot decode file: \"{arg}\"")
            return uerr.RC.DECODE_ERR
        except OSError as e:
            ugen.err(f"OS error; {e.strerror}", nm=data.cmd_nm)
            return uerr.RC.OS_ERR

        for ln in fl_cntnt.splitlines():
            tmp_code = data.exec_fn(ln)
            err_code = err_code or tmp_code

    return err_code
