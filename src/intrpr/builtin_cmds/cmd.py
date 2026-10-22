import subprocess as sp
import sys

from src.utils import err_codes as uerr
from src.utils import gen as ugen

CMD_NM = __name__.split(".")[-1]

OPTS = {
    "STDIN": ("-i", "--stdin"),
}

FLAGS = {
    "CAPTURE-STDOUT": ("-O", "--capture-stdout"),
    "CAPTURE-STDERR": ("-E", "--capture-stderr"),
}

HELP = ugen.HelpObj(
    usage=f"{CMD_NM} [flag ...] [opt] line",
    summary="Execute system shell commands",
    details=(
        "ARGUMENTS",
        ("line", "Line to be executed in the system shell"),
        "OPTIONS",
        (", ".join(OPTS["STDIN"]) + " str", "STDIN to be passed to the line"),
        "FLAGS",
        (", ".join(FLAGS["CAPTURE-STDERR"]), "Capture STDERR"),
        (", ".join(FLAGS["CAPTURE-STDOUT"]), "Capture STDOUT"),
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=1,
    max_args=1,
    opts=tuple(opt for opts in OPTS.values() for opt in opts),
    flags=tuple(flag for flags in FLAGS.values() for flag in flags),
)

ERR_CMD_NOT_SUCCESS = 1000


def run(data: ugen.CmdData) -> int:
    err_code = uerr.RC.ALL_GOOD
    to_run = data.args[0]
    stdin = None
    capture_stdout = False
    capture_stderr = False

    for flag in data.flags:
        if flag in FLAGS["CAPTURE-STDOUT"]:
            capture_stdout = True
        elif flag in FLAGS["CAPTURE-STDERR"]:
            capture_stderr = True

    for opt, val in data.opts.items():
        if opt in OPTS["STDIN"]:
            stdin = val

    compd_proc = sp.run(
        to_run,
        shell=True,
        input=stdin,
        stdout=sp.PIPE if capture_stdout else None,
        stderr=sp.PIPE if capture_stderr else None,
        text=True,
        check=False,
    )
    if compd_proc.returncode != 0:
        err_code = ERR_CMD_NOT_SUCCESS + compd_proc.returncode

    return err_code
