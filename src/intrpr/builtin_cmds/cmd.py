import subprocess as sp
import sys

from src.utils import err_codes as uerr
from src.utils import gen as ugen

CMD_NM = __name__.split(".")[-1]

HELP = ugen.HelpObj(
    usage=f"{CMD_NM} arg [...]",
    summary="(DO NOT USE) Execute strings in the system shell",
    details=(
        "ARGUMENTS",
        ("arg", "Part of line to be executed in the system shell"),
        "OPTIONS",
        ("none", ""),
        "FLAGS",
        ("none", ""),
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=1,
    max_args=float("inf"),
    opts=(),
    flags=()
)

ERR_CMD_NOT_SUCCESS = 1000


def run(data: ugen.CmdData) -> int:
    err_code = uerr.ERR_ALL_GOOD

    try:
        compd_proc = sp.run(
            data.args,
            shell=True,
            capture_output=True,
            text=True,
            check=False
        )
    except UnicodeDecodeError:
        ugen.err("Cannot decode output", nm=data.cmd_nm)
        return uerr.ERR_DECODE_ERR
    if compd_proc.returncode != 0:
        err_code = ERR_CMD_NOT_SUCCESS

    if compd_proc.stderr:
        sys.stderr.write(compd_proc.stderr)
    ugen.write(compd_proc.stdout)
    return err_code
