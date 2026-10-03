import math

from src.utils import err_codes as uerr
from src.utils import gen as ugen

CMD_NM = __name__.split(".")[-1]

HELP = ugen.HelpObj(
    usage=f"{CMD_NM} [opt ...] fl [...]",
    summary="Preview files without opening them fully",
    details=(
        "ARGUMENTS",
        ("fl", "Filename to read"),
        "OPTIONS",
        ("-n num", "Number of lines to read"),
        "FLAGS",
        ("-l", "Show line numbers")
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=1,
    max_args=math.inf,
    opts=("-n",),
    flags=("-l",)
)


def run(data: ugen.CmdData) -> int:
    err_code = uerr.ERR_ALL_GOOD
    num_of_lns = 5
    show_ln_nums = False

    for flag in data.flags:
        if flag == "-l":
            show_ln_nums = True

    for opt in data.opts:
        val = data.opts[opt]
        if opt == "-n":
            try:
                num_of_lns = int(val)
            except ValueError:
                ugen.err(
                    f"Cannot cast to int for '{opt}': '{val}'",
                    nm=data.cmd_nm
                )
                return uerr.ERR_CANT_CAST_VAL

    for arg in data.args:
        try:
            with open(arg) as f:
                cntnt = [ln for _ in range(num_of_lns) if (ln := f.readline())]
        except FileNotFoundError:
            err_code = err_code or uerr.ERR_FL_404
            ugen.err(f"No such file: \"{arg}\"", nm=data.cmd_nm)
            continue
        except PermissionError:
            err_code = err_code or uerr.ERR_PERM_DENIED
            ugen.err(f"Access denied: \"{arg}\"", nm=data.cmd_nm)
            continue
        except IsADirectoryError:
            err_code = err_code or uerr.ERR_IS_A_DIR
            ugen.err(f"Is a directory: \"{arg}\"", nm=data.cmd_nm)
            continue
        except OSError as e:
            err_code = err_code or uerr.ERR_OS_ERR
            ugen.err(f"OS error; {e.strerror}", nm=data.cmd_nm)
            continue

        len_num_lns_avail = len(str(len(cntnt)))
        # Write filename
        ugen.write(ugen.S.fmt(arg, data.is_tty, ugen.S.green_4) + "\n")

        for ln_num, ln in enumerate(cntnt, start=1):
            prefix = ""
            if show_ln_nums:
                prefix = str(ln_num).rjust(len_num_lns_avail) + " "
            ugen.write(prefix + ln)

    return err_code
