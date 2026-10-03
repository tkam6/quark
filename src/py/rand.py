import math
import random
import typing as ty

from src.utils import err_codes as uerr
from src.utils import gen as ugen

CMD_NM = __name__.split(".")[-1]

HELP = ugen.HelpObj(
    usage=f"{CMD_NM} [opt ...] [flag]",
    summary="Get a random number",
    details=(
        "ARGUMENTS",
        ("none", ""),
        "OPTIONS",
        ("-o, --round round", "Number of decimals to round off to"),
        ("-r, --range lower,upper", "Range of random number (int/float)"),
        "FLAGS",
        ("-i, --integer", "Get a random integer")
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=0,
    max_args=0,
    opts=(
        "-o", "--round",
        "-r", "--range"
    ),
    flags=("-i", "--integer")
)

ERR_ROUND_INT = 1000
ERR_FLOAT_FOR_INT = 1001


# What the fuck is this name?
def hdl_rng_diff_typs(opt: str, val: str, cast_fns: tuple[type]) \
        -> tuple[ty.Any] | int:
    split_val = val.split(",")
    if len(split_val) != 2:
        return uerr.ERR_INV_OPT_FMT

    for cast_fn in cast_fns:
        try:
            min_num = cast_fn(split_val[0])
            max_num = cast_fn(split_val[1])
            break
        except ValueError:
            continue
    else:
        return uerr.ERR_CANT_CAST_VAL

    return (min_num, max_num)


def run(data: ugen.CmdData) -> int:
    err_code = uerr.ERR_ALL_GOOD
    valid_rng_typs = (int, float)
    rand_int = False
    round_to = math.inf
    # Exists for the sole purpose of letting the random integer branch know if
    # the default ranges need to be used, because in random integer selection,
    # default range is from 0 to 100.
    use_defa_rng = True
    min_num = 0
    max_num = 1

    for opt in data.opts:
        val = data.opts[opt]
        # Round off places option
        if opt in ("-o", "--round"):
            try:
                round_to = int(val)
            except ValueError:
                ugen.err(
                    f"Cannot cast to int for option '{opt}': '{val}'",
                    nm=data.cmd_nm
                )
                return uerr.ERR_CANT_CAST_VAL

        # Range specifier option
        elif opt in ("-r", "--range"):
            rng = hdl_rng_diff_typs(opt, val, valid_rng_typs)
            if isinstance(rng, int):
                if rng == uerr.ERR_INV_OPT_FMT:
                    ugen.err(
                        f"Invalid value for option '{opt}': '{val}'",
                        nm=data.cmd_nm
                    )
                    return rng
                elif rng == uerr.ERR_CANT_CAST_VAL:
                    ugen.err(
                        f"Expected parts of {' or '.join(i.__name__ for i in valid_rng_typs)} for '{opt}'",
                        nm=data.cmd_nm
                    )
                    return rng
            use_defa_rng = False
            min_num, max_num = rng

    for flag in data.flags:
        # Integer random number flag
        if flag in ("-i", "--integer"):
            rand_int = True

    try:
        round_to_is_inf = math.isinf(round_to)
    except OverflowError:
        ugen.err("Round off overflow: int too big", nm=data.cmd_nm)
        return uerr.ERR_INT_OVERFLOW

    if not round_to_is_inf and rand_int:
        ugen.err("Cannot round integer random numbers", nm=data.cmd_nm)
        return ERR_ROUND_INT
    if rand_int and not type(min_num) == type(max_num) == int:
        ugen.err(
            "Integer random numbers require integer ranges",
            nm=data.cmd_nm
        )
        return ERR_FLOAT_FOR_INT

    if rand_int:
        if use_defa_rng:
            max_num = 100
        if min_num > max_num:
            min_num, max_num = max_num, min_num
        rand_num = random.randint(min_num, max_num)
        ugen.write(str(rand_num) + "\n")
    else:
        rand_num = random.uniform(min_num, max_num)
        if not round_to_is_inf:
            rand_num = round(rand_num, round_to)
        ugen.write(str(rand_num) + "\n")

    return err_code
