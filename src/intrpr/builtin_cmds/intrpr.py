import builtins
import typing as ty

from src.utils import err_codes as uerr
from src.utils import gen as ugen

if ty.TYPE_CHECKING:
    from src.intrpr import internals as iint

CMD_NM = __name__.split(".")[-1]

HELP = ugen.HelpObj(
    usage=(
        f"{CMD_NM} list\n"
        f"{CMD_NM} get name [...]\n"
        f"{CMD_NM} set name value [type]\n"
        f"{CMD_NM} remove name [...]\n"
    ),
    summary="Manage interpreter variables",
    details=(
        "SUBCOMMANDS",
        ("-", "List all variables"),
        ("list", "List all variables"),
        ("get", "Get variables by name"),
        ("set", "Set variables"),
        ("remove", "Remove variables"),
        "ARGUMENTS",
        ("name", "Variable name"),
        ("value", "Variable value"),
        ("type", "Variable type (Python built-in type except NoneType)"),
        "OPTIONS",
        ("none", ""),
        "FLAGS",
        ("-r, --repr", "Output representation of value")
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=0,
    max_args=float("inf"),
    parse_sub_cmds=True,
    sub_cmds={
        None    : (0, 0),
        "set"   : (2, 3),
        "get"   : (1, float("inf")),
        "list"  : (0, 0),
        "remove": (1, float("inf"))
    },
    opts=(),
    flags=("-r", "--repr")
)

ERR_NO_SUCH_BUILTIN_TYP = 1000
ERR_INV_VAL_FOR_TYP = 1001
ERR_TXT_SYN_ERR = 1002
ERR_EXPD_ARGS = 1000
ERR_NO_SUCH_VAR = 1001
ERR_VAR_EXISTS = 1002


def set_vars_helper(
    cmd_nm: str,
    var_nm: str,
    var_typ: str,
    var_val: str,
    intrpr_vars: "iint.IntrprTbl"
) -> int:
    err_code = uerr.ERR_ALL_GOOD

    # If no 3rd argument, type is assumed str, and var_val remains the same
    # 3rd argument passed; type was specified as "None"
    if var_typ == "None":
        if var_val != "None":
            ugen.err(
                f"Invalid value for '{var_typ}': '{var_val}'",
                nm=cmd_nm
            )
        var_val = None
    # 3rd argument passed; type was specified
    elif var_typ != None:
        for nm, obj in vars(builtins).items():
            if nm == var_typ:
                var_obj = obj
                break
        else:
            ugen.err(f"No such type in scope: '{var_typ}'", nm=cmd_nm)
            return ERR_NO_SUCH_BUILTIN_TYP
        try:
            var_val = var_obj(var_val)
        except ValueError:
            ugen.err(
                f"Illegal value for type '{var_typ}': '{var_val}'",
                nm=cmd_nm
            )
            return ERR_INV_VAL_FOR_TYP

    try:
        intrpr_vars[var_nm] = var_val
    except ugen.InvVarTypErr:
        err_code = uerr.ERR_ENV_VAR_INV_TYP
        ugen.err(
            f"Invalid type for '{var_nm}': '{var_val.__class__.__name__}'",
            nm=cmd_nm
        )
    except ugen.InvVarNmErr:
        err_code = uerr.ERR_ENV_VAR_INV_NM
        ugen.err(f"Invalid variable name: '{var_nm}'", nm=cmd_nm)
    except ugen.UnkVarErr:
        err_code = uerr.ERR_ENV_UNK_VAR
        ugen.err(f"Unknown variable: '{var_nm}'", nm=cmd_nm)

    return err_code


def run(data: ugen.CmdData) -> int:
    err_code = uerr.ERR_ALL_GOOD
    repr_val = False

    for flag in data.flags:
        if flag in ("-r", "--repr"):
            repr_val = True

    if data.sub_cmd is None or data.sub_cmd == "list":
        max_nm_len = (
            len(max((i for i in data.intrpr_vars), key=len))
            if data.intrpr_vars else 0
        )
        for nm, val in data.intrpr_vars.items():
            fmted_nm = ugen.S.fmt(nm, data.is_tty, ugen.S.green_4)
            ugen.write(
                (ugen.ljust(fmted_nm, max_nm_len) if data.is_tty else fmted_nm)
                + (" = " if data.is_tty else "=")
                + (repr(val) if repr_val else str(val))
                + "\n"
            )

    elif data.sub_cmd == "get":
        max_arg_len = len(max(data.args, key=len)) if data.args else 0
        for arg in data.args:
            if arg not in data.intrpr_vars:
                ugen.err(f"No such variable: '{arg}'", nm=data.cmd_nm)
                err_code = err_code or uerr.ERR_ENV_UNK_VAR
                continue
            fmted_arg = ugen.S.fmt(arg, data.is_tty, ugen.S.green_4)
            val = data.intrpr_vars[arg]
            val = repr(val) if repr_val else str(val)
            ugen.write(
                (ugen.ljust(fmted_arg, max_arg_len) if data.is_tty else fmted_arg)
                + (" = " if data.is_tty else "=")
                + val
                + "\n"
            )

    elif data.sub_cmd == "set":
        nm = data.args[0]
        val = data.args[1]
        typ = data.args[2] if len(data.args) == 3 else None
        tmp_err_code = set_vars_helper(
            data.cmd_nm,
            nm,
            typ,
            val,
            data.intrpr_vars
        )
        err_code = err_code or tmp_err_code

    elif data.sub_cmd == "remove":
        for arg in data.args:
            if arg not in data.intrpr_vars:
                ugen.err(f"No such variable: '{arg}'", nm=data.cmd_nm)
                err_code = err_code or uerr.ERR_ENV_UNK_VAR
                continue
            try:
                data.intrpr_vars.pop(arg)
            except ugen.InvAccess:
                ugen.err(
                    f"Cannot remove protected variable: {arg}",
                    nm=data.cmd_nm
                )

    return err_code
