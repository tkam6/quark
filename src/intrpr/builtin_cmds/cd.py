import os
import pathlib as pl
import typing as ty

from src.utils import err_codes as uerr
from src.utils import gen as ugen

if ty.TYPE_CHECKING:
    from src.intrpr import internals as iint

CMD_NM = __name__.split(".")[-1]

HELP = ugen.HelpObj(
    usage=f"{CMD_NM} [flag ...] [pth]",
    summary="Change working directory",
    details=(
        "ARGUMENTS",
        ("none", "Change to user directory"),
        ("pth", "Directory to change to"),
        "OPTIONS",
        ("none", ""),
        "FLAGS",
        ("-", "Change to directory previously in"),
        ("-p", "Print directory after changing to it"),
        ("-m", "Create directories before changing"),
        ("-t", "Create temporary directory and change to it")
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=0,
    max_args=1,
    opts=(),
    flags=("-", "-p", "-m", "-t")
)

ERR_CANT_ALLOT_TMP_DIR = 1000


def actually_chg_dir(
    cmd_nm: str,
    pth: str,
    prn_dir: bool,
    intrpr_vars: "iint.IntrprTbl"
) -> int:
    err_code = uerr.ERR_ALL_GOOD

    try:
        before = os.getcwd()
        os.chdir(os.path.expanduser(pth))
        intrpr_vars["_PREV_CWD_"] = before
        if prn_dir:
            ugen.write(pth + "\n")
    except FileNotFoundError:
        err_code = uerr.ERR_DIR_404
        ugen.err(f"No such directory: \"{pth}\"", nm=cmd_nm)
    except NotADirectoryError:
        err_code = uerr.ERR_NOT_A_DIR
        ugen.err(f"Not a directory: \"{pth}\"", nm=cmd_nm)
    except PermissionError:
        err_code = uerr.ERR_PERM_DENIED
        ugen.err(f"Access denied: \"{pth}\"", nm=cmd_nm)
    # Don't think this is reachable, but let's be on the safer side
    except OSError as e:
        err_code = uerr.ERR_OS_ERR
        ugen.err(f"OS error; {e.strerror}", nm=cmd_nm)

    return err_code


def run(data: ugen.CmdData) -> int:
    chg_to: pl.Path | str

    err_code = uerr.ERR_ALL_GOOD
    chg_to_prev_cwd = False
    prn_dir = False
    mk_dirs = False
    tmp_dir = False

    for flag in data.flags:
        if flag == "-":
            chg_to_prev_cwd = True
        elif flag == "-p":
            prn_dir = True
        elif flag == "-m":
            mk_dirs = True
        elif flag == "-t":
            tmp_dir = True

    if chg_to_prev_cwd and data.args:
        ugen.err(
            "Cannot change to previous and specified directory simultaneously",
            nm=data.cmd_nm
        )
        return uerr.ERR_INV_USAGE

    if chg_to_prev_cwd and tmp_dir:
        ugen.err(
            "Cannot change to previous and temporary directory simultaneously",
            nm=data.cmd_nm
        )
        return uerr.ERR_INV_USAGE

    # Change to previous directory option
    if chg_to_prev_cwd:
        chg_to = data.intrpr_vars["_PREV_CWD_"]

    # Temporary directory
    elif tmp_dir:
        for i in range(100):
            dir_pth = f"/tmp/quark_cd_{i}/"
            try:
                os.makedirs(dir_pth)
            except FileExistsError:
                continue
            chg_to = dir_pth
            break
        else:
            ugen.err(
                "Too unlucky... cannot allot temporary directory",
                nm=data.cmd_nm
            )
            return ERR_CANT_ALLOT_TMP_DIR

    elif data.args:
        chg_to = data.args[0]

    else:
        chg_to = os.path.expanduser("~")

    # Make directories before changing
    if mk_dirs:
        try:
            os.makedirs(chg_to, exist_ok=True)
        except FileExistsError:
            ugen.err(
                f"Cannot make directory; File exists: \"{chg_to}\"",
                nm=data.cmd_nm
            )
            return uerr.ERR_FL_EXISTS
        except PermissionError:
            ugen.err(
                f"Cannot make directory; Access denied: \"{chg_to}\"",
                nm=data.cmd_nm
            )
            return uerr.ERR_PERM_DENIED
        except OSError as e:
            ugen.err(f"OS error; {e.strerror}", nm=data.cmd_nm)
            return uerr.ERR_OS_ERR

    err_code = actually_chg_dir(data.cmd_nm, chg_to, prn_dir, data.intrpr_vars)
    return err_code
