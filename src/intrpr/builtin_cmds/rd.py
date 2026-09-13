from src.utils import err_codes as uerr
from src.utils import gen as ugen

CMD_NM = __name__.split(".")[-1]

HELP = ugen.HelpObj(
    usage=f"{CMD_NM} [opt] ident [type]",
    summary="Read input into variable",
    details=(
        "ARGUMENTS",
        ("ident", "Identifier to read input into"),
        ("type", "Builtin type to cast value into"),
        "OPTIONS",
        ("-p, --prompt", "Prompt text"),
        "FLAGS",
        ("-g, --getch", "Get a single character immediately")
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=1,
    max_args=1,
    opts=("-p", "--prompt"),
    flags=("-g", "--getch")
)

ERR_NO_SUCH_BUILTIN_TYP = 1000
ERR_INV_VAL_FOR_TYP = 1001


def run(data: ugen.CmdData) -> int:
    err_code = uerr.ERR_ALL_GOOD
    prompt = ""
    single_chr = False
    ident = data.args[0]

    for flag in data.flags:
        if flag in ("-g", "--getch"):
            single_chr = True
    for opt, val in data.opts.items():
        if opt in ("-p", "--prompt"):
            prompt = val

    ugen.write(prompt, flush=True)
    if single_chr:
        inp_hdlr = ugen.InpHdlr()
        inp_hdlr.set_new_sett()
        try:
            inp = inp_hdlr.getch()
        finally:
            inp_hdlr.reset_sett()
        ugen.write("\n")
    else:
        inp = input()

    data.env_vars[ident] = inp
    return err_code
