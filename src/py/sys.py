import os
import platform as pf
import pwd
import socket

import src.utils.err_codes as uerr
import src.utils.gen as ugen

BEHAVIOUR_FLAGS = {
    "NO-HEADERS": ("-H", "--no-headers"),
}

DISP_ARGS = {
    "archi"   : "architecture",
    "host"    : "hostname",
    "kernel"  : "kernel",
    "os"      : "os",
    "uid"     : "user-id",
    "user"    : "username",
}

DISP_FLAGS = {
    "-a"        : "architecture",
    "--archi"   : "architecture",
    "-h"        : "hostname",
    "--host"    : "hostname",
    "-i"        : "user-id",
    "-k"        : "kernel",
    "--kernel"  : "kernel",
    "-o"        : "os",
    "--os"      : "os",
    "--uid"     : "user-id",
    "-u"        : "username",
    "--user"    : "username",
}

HELP = ugen.HelpObj(
    usage="",
    summary="",
    details=(""),
)

CMD_SPEC = ugen.CmdSpec(
    min_args=0,
    max_args=float("inf"),
    opts=(),
    flags=tuple(DISP_FLAGS) + tuple(flag for flags in BEHAVIOUR_FLAGS.values() for flag in flags),
)

RC_INV_ARG = 1000


def run(data: ugen.CmdData) -> int:
    err_code = uerr.RC.ALL_GOOD
    headers = True
    what_to_disp = [None] * (len(data.args) + len(data.opts) + len(data.flags))

    for flag_num, flag in enumerate(data.flags):
        if flag in DISP_FLAGS:
            what_to_disp[data.flag_idxs[flag_num]] = DISP_FLAGS[flag]
        elif flag in BEHAVIOUR_FLAGS["NO-HEADERS"]:
            headers = False

    for arg_num, arg in enumerate(data.args):
        if arg not in DISP_ARGS:
            ugen.err(f"Whoopsa-daisy, what do we havvvve here? '{arg}'")
            return RC_INV_ARG
        what_to_disp[data.arg_idxs[arg_num]] = DISP_ARGS[arg]

    what_to_disp = list(dict.fromkeys(i for i in what_to_disp if i is not None))

    max_field_len = 0
    try:
        max_field_len = len(max(what_to_disp, key=len))
    except ValueError:
        pass

    for field in what_to_disp:
        header = f"{field:<{max_field_len}}: " if headers else ""
        if field == "hostname":
            ugen.write(f"{header}{socket.getfqdn()}\n")
        elif field == "user-id":
            ugen.write(f"{header}{os.getuid()}\n")
        elif field == "username":
            ugen.write(f"{header}{pwd.getpwuid(os.getuid()).pw_name}\n")
        elif field == "kernel":
            ugen.write(f"{header}{pf.release()}\n")
        elif field == "os":
            ugen.write(f"{header}{pf.system()}\n")
        elif field == "architecture":
            ugen.write(f"{header}{pf.machine()}\n")

    return err_code
