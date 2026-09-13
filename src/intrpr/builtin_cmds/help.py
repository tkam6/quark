import math
import os
import typing as ty

from src.utils import consts as uconst
from src.utils import err_codes as uerr
from src.utils import gen as ugen

if ty.TYPE_CHECKING:
    from src.intrpr import cmd_reslvr as icres
    from src.intrpr import internals as iint

CMD_NM = __name__.split(".")[-1]

HELP = ugen.HelpObj(
    usage=f"{CMD_NM} [cmd ...]",
    summary="Display help for commands",
    details=(
        "ARGUMENTS",
        ("none", "Display help summaries of built-in commands"),
        ("cmd", "Command to fetch help text for"),
        "OPTIONS",
        ("none", ""),
        "FLAGS",
        ("-a, --all", "Display help summaries of all recognised commands"),
        ("-e, --external", "Display help summaries of external commands"),
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=0,
    max_args=math.inf,
    opts=(),
    flags=(
        "-a", "--all",
        "-e", "--external"
    )
)

ERR_NO_SUCH_CMD = 1000
ERR_MSG_MAP = {
    uerr.ERR_BAD_CMD: "No such command",
    uerr.ERR_NO_HELP_OBJ: "No help object",
    uerr.ERR_INV_HELP_OBJ: "Invalid help object",
    uerr.ERR_NO_CMD_FN: "No command function",
    uerr.ERR_INV_NUM_PARAMS: "Invalid command function",
    uerr.ERR_NO_CMD_SPEC: "No command spec",
    uerr.ERR_INV_CMD_SPEC: "Invalid command spec",
    uerr.ERR_CANT_LD_CMD_MOD: "Could not load command module",
    uerr.ERR_CMD_SYN_ERR: "Syntax error in command module",
}


class Out:
    def __init__(self, cmd: str, help_str: str, nl_after_cmd: bool) -> None:
        self.cmd = cmd
        self.help_str = help_str
        self.nl_after_cmd = nl_after_cmd


class Err:
    def __init__(self, msg: str, code: int) -> None:
        self.msg = msg
        self.code = code


def cons_detailed_help_str(
    help_obj: ugen.HelpObj,
    term_sz: os.terminal_size,
    is_tty: bool
) -> str:
    # TODO: Make the padding only depend on parameter names of the current
    # section, like separate padding amounts for "ARGUMENTS", "OPTIONS",
    # "FLAGS"
    details_str = []
    max_param_len = 0
    max_sgl_ln_param_len = 10
    tab = "\t".expandtabs(uconst.TAB_SZ)

    # To determine maximum length of arguments, options and flags
    for i in help_obj.details:
        if isinstance(i, str):
            continue
        # If the length of the parameter is longer than the maximum accepted
        # length for same-line printing, then it shouldn't accept the maximum
        # parameter length, which is used to determine padding for same-line
        # printing
        if len(i[0]) > max_sgl_ln_param_len:
            continue
        max_param_len = max(max_param_len, len(i[0]))

    for i in help_obj.details:
        nl = False
        # For heading like "ARGUMENTS", "OPTIONS", "FLAGS"...
        if isinstance(i, str):
            details_str.append(ugen.S.fmt(i, is_tty, ugen.S.magenta_4))
            continue
        if len(i[0]) > max_param_len:
            nl = True
        # Newline and same line mixed format detailed help strings
        clred_i0 = ugen.S.fmt(i[0], is_tty, ugen.S.blue_4)
        wrap_amt = term_sz.columns - len(2 * tab + max_param_len * " " + tab)
        full_ln = (
            tab
            + (clred_i0 if nl else (ugen.ljust(clred_i0, max_param_len) + tab))
            + (("\n" + 2 * tab + max_param_len * " " + tab) if nl else "")
        )
        for idx, each_ln in enumerate(i[1].splitlines()):
            string = [each_ln[j : j + wrap_amt] for j in range(0, len(each_ln), wrap_amt)]
            full_ln += (
                ("\n" if idx != 0 else "")
                + ((2 * tab + max_param_len * " " + tab) if idx >= 1 else "")
                + (2 * tab + max_param_len * " " + tab).join(string)
            )
        details_str.append(full_ln)

    # To support multiline usage strings
    usage_str = []
    for usage_ln in help_obj.usage.splitlines():
        usage_str.append(tab * 2 + usage_ln)

    return (
        tab + help_obj.summary + "\n"                                   # Summary ending in newline
        + tab + ugen.S.fmt("USAGE", is_tty, ugen.S.magenta_4) + "\n"    # Usage header
        + "\n".join(usage_str) + "\n"                                   # Usage (multiline supported)
        + tab + ("\n" + tab).join(details_str)                          # Details (multiline supported for each entry)
    )


def get_detailed_help(
    cmd_reslvr: "icres.CmdReslvr",
    ext_cached_cmds: dict[str, "iint.CmdCacheEntry"],
    pths: tuple[str, ...],
    args: tuple[str, ...],
    term_sz: os.terminal_size,
    is_tty: bool
) -> list[Out | Err]:
    op_buf: list[Out | Err]
    op_buf = []

    for cmd_nm in args:
        # Built-in command help
        help_obj = cmd_reslvr.get_builtin_help(cmd_nm)
        if isinstance(help_obj, ugen.HelpObj):
            op_buf.append(Out(
                ugen.S.fmt(cmd_nm, is_tty, ugen.S.green_4),
                cons_detailed_help_str(help_obj, term_sz, is_tty),
                nl_after_cmd=True
            ))
            continue
        # External command help
        help_obj = cmd_reslvr.get_ext_help(cmd_nm, ext_cached_cmds, pths)
        if isinstance(help_obj, ugen.HelpObj):
            op_buf.append(Out(
                ugen.S.fmt(cmd_nm, is_tty, ugen.S.green_4),
                cons_detailed_help_str(help_obj, term_sz, is_tty),
                nl_after_cmd=True
            ))
            continue

        err_ret = help_obj
        to_disp = "Where's the error message?"
        err_msg = ERR_MSG_MAP.get(err_ret)
        if err_msg is not None:
            to_disp = f"{err_msg}: '{cmd_nm}'"
        op_buf.append(Err(to_disp, help_obj))

    return op_buf


def run(data: ugen.CmdData) -> int:
    op_buf: list[Out | Err]

    err_code = uerr.ERR_ALL_GOOD
    cmd_reslvr = data.cmd_reslvr
    all_cmds = False
    ext_cmds = False

    for flag in data.flags:
        if flag in ("-a", "--all"):
            all_cmds = True
        elif flag in ("-e", "--external"):
            ext_cmds = True

    if (all_cmds or ext_cmds) and data.args:
        ugen.err(
            "Cannot use all or external command flags for detailed help",
            nm=data.cmd_nm
        )
        return uerr.ERR_INV_USAGE
    if all_cmds and ext_cmds:
        ugen.err(
            "Cannot use all and external command flags simultaneously",
            nm=data.cmd_nm
        )
        return uerr.ERR_INV_USAGE

    op_buf = []
    max_arg_len = 0

    if not data.args:
        # Either all commands or just built-in ones
        if all_cmds or not ext_cmds:
            # Run, run, RUNNNNN through the built-ins available
            for elem in cmd_reslvr.builtin_cmds:
                op_buf.append(Out(
                    ugen.S.fmt(elem, data.is_tty, ugen.S.green_4),
                    cmd_reslvr.get_builtin_help(elem).summary,
                    False
                ))
                max_arg_len = max(max_arg_len, len(elem))

        # Either all commands or just external ones
        if all_cmds or ext_cmds:
            cmd_nm_arr = []
            pths = data.intrpr_vars["PTH"]
            # Run, run, RUNNNNN through paths in the path variable
            for pth in pths:
                try:
                    for item in os.listdir(pth):
                        if not os.path.isfile(os.path.join(pth, item)):
                            continue
                        if not item.endswith(".py"):
                            continue
                        cmd_nm_arr.append(os.path.splitext(item)[0])
                except FileNotFoundError:
                    continue

            for cmd_nm in cmd_nm_arr:
                retd = cmd_reslvr.get_ext_help(
                    cmd_nm,
                    data.ext_cached_cmds,
                    pths
                )
                if isinstance(retd, int):
                    # If there was no help object (uerr.ERR_NO_HELP_OBJ), don't
                    # report, as this is the listing of all summaries
                    if retd == uerr.ERR_NO_HELP_OBJ:
                        pass
                    elif retd == uerr.ERR_INV_HELP_OBJ:
                        op_buf.append(Err(
                            f"Invalid help object: '{cmd_nm}'",
                            uerr.ERR_INV_HELP_OBJ
                        ))
                    elif retd == uerr.ERR_CANT_LD_CMD_MOD:
                        op_buf.append(Err(
                            f"Could not load command module: '{cmd_nm}'",
                            uerr.ERR_CANT_LD_CMD_MOD
                        ))
                    continue

                op_buf.append(Out(
                    ugen.S.fmt(cmd_nm, data.is_tty, ugen.S.green_4),
                    retd.summary,
                    nl_after_cmd=False
                ))
                max_arg_len = max(max_arg_len, len(cmd_nm))

    # Otherwise, print detailed help text for args
    else:
        op_buf.extend(get_detailed_help(
            cmd_reslvr,
            data.ext_cached_cmds,
            data.intrpr_vars["PTH"],
            data.args,
            data.term_sz,
            data.is_tty
        ))

    # To compensate for the colon character when all command help listing
    # takes place. Is modified here because detailed command listing doesn't
    # need max_arg_len
    max_arg_len += 1
    # Finally, write output to STDOUT and STDERR
    for i in op_buf:
        if isinstance(i, Err):
            err_code = err_code or i.code
            ugen.err(i.msg, nm=data.cmd_nm)
            continue

        cmd_nm = i.cmd
        if not i.nl_after_cmd:
            cmd_nm = ugen.ljust((cmd_nm + ":"), max_arg_len)

        ugen.write(
            cmd_nm
            + ("\n" if i.nl_after_cmd else " ")
            + i.help_str
            + "\n"
        )

    return err_code
