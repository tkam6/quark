import sys

from src.utils import err_codes as uerr
from src.utils import gen as ugen

CMD_NM = __name__.split(".")[-1]

HELP = ugen.HelpObj(
    usage=f"{CMD_NM} [flag] [code]",
    summary="Exit the interpreter",
    details=(
        "ARGUMENTS",
        ("code", "Exit code to return to calling program"),
        "OPTIONS",
        ("none", ""),
        "FLAGS",
        ("-T, --no-exit-text", "Suppress exit text"),
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=0,
    max_args=1,
    opts=(),
    flags=("-T", "--no-exit-text")
)


def run(data: ugen.CmdData) -> int:
    exit_code = uerr.ERR_ALL_GOOD
    exit_txt = not ("-T" in data.flags or "--no-exit-text" in data.flags)

    if data.args:
        exit_code = data.args[0]
        try:
            exit_code = int(exit_code)
        except ValueError:
            ugen.err(f"Cannot cast to int: '{exit_code}'", nm=data.cmd_nm)
            return uerr.ERR_CANT_CAST_VAL
        except OverflowError:
            ugen.err("Integer overflow", nm=data.cmd_nm)
            return uerr.ERR_INT_OVERFLOW

    if exit_txt:
        ugen.write("bye\n")
    sys.exit(exit_code)
