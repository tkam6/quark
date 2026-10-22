import typing as ty

from src.utils import err_codes as uerr
from src.utils import gen as ugen

if ty.TYPE_CHECKING:
    from src.parser import ast_nodes as past


def classi_params(
    cmd_nm: str,
    params: "list[past.Param]",
    cmd_spec: ugen.CmdSpec,
) -> tuple[
    str | None,
    tuple[str, ...],
    dict[str, str],
    tuple[str, ...]
] | int:
    args = []
    opts = {}
    flags = []
    arg_idxs = []
    opt_idxs = []
    flag_idxs = []
    arg_cnt = 0
    skip = 0
    params_len = len(params)

    # Iterate through the parser output
    for idx, param in enumerate(params):
        param_val = param.val
        if skip:
            skip -= 1
            continue

        # LONG-FORM OPTIONS AND FLAGS
        if param_val.startswith("--") and not param.escd_hyp:
            # Flags are given more preference
            if param_val in cmd_spec.flags:
                flags.append(param_val)
                flag_idxs.append(idx)
            # Then options
            elif param_val in cmd_spec.opts:
                if idx >= params_len - 1:
                    ugen.err(
                        f"Expected value for option '{param_val}'",
                        nm=cmd_nm,
                    )
                    return uerr.RC.EXPD_VAL_OPT
                opts[param_val] = params[idx + 1].val
                opt_idxs.append(idx)
                skip += 1
            # Invalid long-form option/flag
            else:
                ugen.err(f"Invalid option/flag: '{param_val}'", nm=cmd_nm)
                return uerr.RC.INV_OPTS_FLAGS
            continue

        # SHORT-FORM OPTIONS AND FLAGS, OR COMBINED SHORT-FORM FLAGS
        if (
            param_val.startswith("-")
            and not param_val.startswith("--")
            and not param.escd_hyp
        ):
            if param_val in cmd_spec.flags:
                flags.append(param_val)
                flag_idxs.append(idx)
            elif param_val in cmd_spec.opts:
                if idx >= params_len - 1:
                    ugen.err(
                        f"Expected value for option '{param_val}'",
                        nm=cmd_nm
                    )
                    return uerr.RC.EXPD_VAL_OPT
                opts[param_val] = params[idx + 1].val
                opt_idxs.append(idx)
                skip += 1
            else:
                # Lone '-'
                if not param_val[1 :]:
                    ugen.err(
                        f"Invalid option/flag: '{param_val}'",
                        nm=cmd_nm,
                    )
                    return uerr.RC.INV_OPTS_FLAGS
                # Combined short flags
                for i in param_val[1 :]:
                    if "-" + i in cmd_spec.flags:
                        flags.append("-" + i)
                        flag_idxs.append(idx)
                        continue
                    ugen.err(
                        f"Invalid option/flag: '{param_val}'",
                        nm=cmd_nm,
                    )
                    return uerr.RC.INV_OPTS_FLAGS
            continue

        # ARGUMENTS
        arg_cnt += 1
        if arg_cnt > cmd_spec.max_args:
            ugen.err(
                f"Argument overflow; {arg_cnt} not in [{cmd_spec.min_args}, {cmd_spec.max_args}]",
                nm=cmd_nm,
            )
            return uerr.RC.UNEXPD_ARGS
        args.append(param_val)
        arg_idxs.append(idx)

    if arg_cnt < cmd_spec.min_args:
        ugen.err(
            f"Argument underflow; {arg_cnt} not in [{cmd_spec.min_args}, {cmd_spec.max_args}]",
            nm=cmd_nm,
        )
        return uerr.RC.INSUFF_ARGS

    # Horrendous
    sub_cmd = None
    if cmd_spec.parse_sub_cmds:
        sub_cmd = sub_cmd if args == [] else args.pop(0)
        arg_cnt = len(args)
        # Subcommand is not present in the command spec
        if sub_cmd not in cmd_spec.sub_cmds:
            if sub_cmd is None:
                ugen.err("Expected subcommand", nm=cmd_nm)
                return uerr.RC.EXPD_SUB_CMD
            else:
                ugen.err(f"Invalid subcommand: '{sub_cmd}'", nm=cmd_nm)
                return uerr.RC.INV_SUB_CMD
        # Check if number of arguments supplied is correct for the
        # subcommand
        lower_lt = cmd_spec.sub_cmds[sub_cmd][0]
        upper_lt = cmd_spec.sub_cmds[sub_cmd][1]
        if arg_cnt < lower_lt:
            ugen.err(
                (
                    "Argument underflow"
                    + (f" ({sub_cmd})" if sub_cmd is not None else "")
                    + f"; {arg_cnt} not in [{lower_lt}, {upper_lt}]"
                ),
                nm=cmd_nm,
            )
            return uerr.RC.INSUFF_ARGS
        elif arg_cnt > upper_lt:
            ugen.err(
                (
                    "Unexpected arguments"
                    + (f" ({sub_cmd})" if sub_cmd is not None else "")
                    + f"; {arg_cnt} not in [{lower_lt}, {upper_lt}]"
                ),
                nm=cmd_nm,
            )
            return uerr.RC.UNEXPD_ARGS

    return (
        sub_cmd,
        tuple(args),
        opts,
        tuple(flags),
        tuple(arg_idxs),
        tuple(opt_idxs),
        tuple(flag_idxs),
    )
