import time

from src.utils import err_codes as uerr
from src.utils import gen as ugen

CMD_NM = __name__.split(".")[-1]

HELP = ugen.HelpObj(
    usage=f"{CMD_NM} line",
    summary="Time command execution",
    details=(
        "ARGUMENTS",
        ("line", "Line to execute"),
        "OPTIONS",
        (
            "-e, --expo num",
            ("Negative exponent of 10 to divide elapsed time with\n"
             "0 <= num <= 9, num -> int")
        ),
        "FLAGS",
        ("none", ""),
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=1,
    max_args=1,
    opts=("-e", "--expo"),
    flags=()
)

ERR_EXPO_OUTSIDE_RNG = 1000
EXPO_UNIT_MAP = {
    0: "s",
    3: "ms",
    6: "us",
    9: "ns"
}


def run(data: ugen.CmdData) -> int:
    err_code = uerr.ERR_ALL_GOOD
    expo = 3

    for opt, val in data.opts.items():
        if opt in ("-e", "--expo"):
            try:
                int(val)
            except ValueError:
                ugen.err(
                    f"Cannot cast to int (option {opt}): '{val}'",
                    nm=data.cmd_nm
                 )
                return uerr.ERR_CANT_CAST_VAL
            expo = int(val)
            if expo not in range(10):
                ugen.err(
                    f"Exponent value outside range: {val} [0 <= expo <= 9]",
                    nm=data.cmd_nm
                )
                return ERR_EXPO_OUTSIDE_RNG

    start = time.perf_counter_ns()
    data.exec_fn(data.args[0])
    elapsed = time.perf_counter_ns() - start
    unit = EXPO_UNIT_MAP.get(expo)
    if unit is None:
        unit = f"e-{expo}s"
    elapsed_disp = elapsed / 10 ** (9 - expo)
    ugen.write(f"elapsed {elapsed_disp:.3f}{unit}\n")
    return err_code
