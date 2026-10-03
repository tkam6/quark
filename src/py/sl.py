from src.utils import err_codes as uerr
from src.utils import gen as ugen

HELP = ugen.HelpObj(
    usage="",
    summary="",
    details=()
)
CMD_SPEC = ugen.CmdSpec(min_args=0, max_args=0, opts=(), flags=())


def run(data: ugen.CmdData) -> int:
    err_code = uerr.ERR_ALL_GOOD
    data.exec_fn("sl")
    return err_code
