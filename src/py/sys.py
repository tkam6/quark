import utils.err_codes as uerr
import utils.gen as ugen

HELP =  ugen.HelpObj(

)

CMD_SPEC = ugen.CmdSpec(

)

def run(data: ugen.CmdData) -> int:
    err_code = uerr.RC.ALL_GOOD
    return err_code
