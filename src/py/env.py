import typing as ty

from src.utils import err_codes as uerr
from src.utils import gen as ugen

CMD_NM = __name__.split(".")[-1]

HELP = ugen.HelpObj(
    usage=(
        f"{CMD_NM} list\n"
        f"{CMD_NM} get name [...]\n"
        f"{CMD_NM} set name value\n"
        f"{CMD_NM} rm name [...]\n"
    ),
    summary="Manage environment variables",
    details=(
        "SUBCOMMANDS",
        ("-", "List all variables"),
        ("clr", "Clear all variables"),
        ("list", "List all variables"),
        ("get", "Get variables by name"),
        ("set", "Set variables"),
        ("rm", "Remove variables"),
        "ARGUMENTS",
        ("name", "Variable name"),
        ("value", "Variable value"),
        "OPTIONS",
        ("none", ""),
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=0,
    max_args=float("inf"),
    parse_sub_cmds=True,
    sub_cmds={
        None    : (0, 0),
        "clr"   : (0, 0),
        "set"   : (2, 2),
        "get"   : (1, float("inf")),
        "list"  : (0, 0),
        "rm": (1, float("inf"))
    },
    opts=(),
    flags=("-r", "--raw")
)

ERR_INV_VAL_FOR_TYP = 1000
ERR_TXT_SYN_ERR = 1001
ERR_EXPD_ARGS = 1002
ERR_NO_SUCH_VAR = 1003
ERR_VAR_EXISTS = 1004


class Err(ty.NamedTuple):
    msg: str


class Out(ty.NamedTuple):
    nm: str
    val: str


def run(data: ugen.CmdData) -> int:
    err_code = uerr.ERR_ALL_GOOD
    raw_val = False
    op_buf = []
    max_nm_len = 0

    for flag in data.flags:
        if flag in ("-r", "--raw"):
            raw_val = True

    if data.sub_cmd is None or data.sub_cmd == "list":
        for (nm, val) in data.env_vars:
            op_buf.append(Out(nm, val if raw_val else ugen.esc_chrs_all(val)))
            max_nm_len = max(max_nm_len, len(nm))

    elif data.sub_cmd == "clr":
        for (key, val) in data.env_vars:
            data.env_vars.rm(key)

    elif data.sub_cmd == "get":
        for arg in data.args:
            if arg not in data.env_vars:
                err_code = err_code or uerr.ERR_ENV_UNK_VAR
                op_buf.append(Err(f"No such variable: {arg}"))
                continue
            val = data.env_vars[arg]
            op_buf.append(Out(arg, val if raw_val else ugen.esc_chrs_all(val)))
            max_nm_len = max(max_nm_len, len(arg))

    elif data.sub_cmd == "set":
        data.env_vars[data.args[0]] = data.args[1]

    elif data.sub_cmd == "rm":
        for arg in data.args:
            if arg not in data.env_vars:
                err_code = err_code or uerr.ERR_ENV_UNK_VAR
                op_buf.append(Err(f"No such variable: '{arg}'"))
                continue
            data.env_vars.rm(arg)

    for item in op_buf:
        if isinstance(item, Err):
            ugen.err(item.msg, nm=data.cmd_nm)
            continue
        clred_nm = ugen.S.fmt(item.nm, data.is_tty, ugen.S.green_4)
        ugen.write(
            (ugen.ljust(clred_nm, max_nm_len) if data.is_tty else clred_nm)
            + (" = " if data.is_tty else "=")
            + "'" + item.val + "'"
            + "\n"
        )
    return err_code
