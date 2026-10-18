from src.utils import err_codes as uerr
from src.utils import gen as ugen

CMD_NM = __name__.split(".")[-1]

HELP = ugen.HelpObj(
    usage=f"{CMD_NM} fl [...]",
    summary="Run a script in the current process",
    details=(
        "ARGUMENTS",
        ("fl", "Script to run"),
        "OPTIONS",
        ("none", ""),
        "FLAGS",
        ("none", "")
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=1,
    max_args=float("inf"),
    opts=(),
    flags=()
)

ERR_FROM_CMD = 1000


def run(data: ugen.CmdData) -> int:
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

    err = uerr.RC.ALL_GOOD
    for ln in fl_cntnt.splitlines():
        tmp = data.exec_fn(ln)
        err = err or tmp

    err_code = uerr.RC.ALL_GOOD
    if err:
        err_code = ERR_FROM_CMD
    data.intrpr_vars["_RN_CMD_RET_"] = err
    return err_code
