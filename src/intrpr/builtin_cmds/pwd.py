import os

from src.utils import err_codes as uerr
from src.utils import gen as ugen

CMD_NM = __name__.split(".")[-1]

HELP = ugen.HelpObj(
    usage=CMD_NM,
    summary="Print the current working directory",
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
    max_args=0,
    opts=(),
    flags=()
)


def run(data: ugen.CmdData) -> int:
    err_code = uerr.RC.ALL_GOOD

    try:
        ugen.write(os.getcwd() + "\n")
    # Don't know if this is possible... but just in case
    except PermissionError:
        err_code = uerr.RC.PERM_DENIED
        ugen.err("Access denied", nm=data.cmd_nm)

    return err_code

