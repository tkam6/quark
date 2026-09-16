#!/usr/bin/env -S python3 -BOO
import dataclasses as dcs
import os
import signal as sig
import sys
import traceback as tb

from src.intrpr import cfg_mgr as cmgr
from src.intrpr import eng as ieng
from src.logger import eng as leng
from src.utils import consts as uconst
from src.utils import err_codes as uerr
from src.utils import gen as ugen

if not sys.argv:
    # PROG = "[main]"
    ugen.fatal("What kind of sorcery is this? Why is the program run this way? (sys.argv is empty)")
PROG = sys.argv[0]
# Nuitka overwrites sys.argv[0], and provides __compiled__ with original argv
if "__compiled__" in locals():
    PROG = __compiled__.original_argv0         # noqa: F821

VER = uconst.VER
MIN_ARGS = 0
MAX_ARGS = 1
OPTS = {
    "DEBUG-TIME-UNIT": ("-t", "--debug-time-unit"),
    "LINE-MODE": ("-l", "--line-mode"),
}
FLAGS = {
    "DEBUG": ("-d", "--debug"),
    "HELP": ("-h", "--help"),
    "INFO": ("-i", "--info"),
    "LOAD-EXTERNAL": ("-p", "--preload-external"),
    "NO-WARNINGS": ("-W", "--no-warnings"),
    "STDERR-ANSI": ("-e", "--preserve-stderr-ANSI"),
    "STDOUT-ANSI": ("-o", "--preserve-stdout-ANSI"),
}

# TODO: Update the help string
HELP_TXT = (
    "USAGE",
    f"\t{PROG} [flag ...] [opt val ...] [file]",
    "ARGUMENTS",
    "\tfl          Script to run",
    "OPTIONS",
    "\t-l, --line-mode",
    "\t            Line mode to use for input",
    "\t            Valid: 'emacs', 'vi', 'raw'",
    "\t-t, --debug-time-unit unit",
    "\t            Unit for debugging time output",
    "\t            Valid: 'ns', 'us', 'ms', 's'",
    "FLAGS",
    "\t-d, --debug",
    "\t            Show debug messages",
    "\t-e, --preserve-ANSI-stderr",
    "\t            Preserve ANSI codes in STDERR redirects",
    "\t-h, --help  Display help text",
    "\t-i, --info  Show info messages",
    "\t-o, --preserve-ANSI-stdout",
    "\t            Preserve ANSI codes in STDOUT redirects",
    "\t-p, --load-external",
    "\t            Load all external commands on startup",
    "\t-W, --no-warnings",
    "\t            Suppress warnings",
)


@dcs.dataclass
class MainProgParsed:
    ln_mode: str = "default"
    pre_ld_ext_cmds: bool = False
    stdout_ansi: bool = False
    stderr_ansi: bool = False
    log_lvl: int = leng.LogLvls.WARN
    debug_time_expo: int = 6
    fl: str | None = None


def parse_argv(cfg: MainProgParsed, passed_params: list[str]) -> MainProgParsed:
    params = passed_params.copy()
    parse_opts_flags = True
    args = []
    idx = 0
    all_flags = tuple(flag for flags in FLAGS.values() for flag in flags)
    all_flags_opts = (
        *all_flags,
        *(opt for opts in OPTS.values() for opt in opts),
    )

    while idx < len(params):
        param = params[idx]
        if not param.startswith("-") or not parse_opts_flags:
            args.append(param)
            idx += 1
            continue
        if param == "--":
            parse_opts_flags = False
            idx += 1
            continue
        if param not in all_flags_opts:
            if [i for i in param[1 :] if f"-{i}" not in all_flags]:
                ugen.fatal_Q(f"Unknown parameter: '{param}'")
                sys.exit(uerr.ERR_MP_UNK_TOK)
            params[idx : idx + 1] = list(param[1 :])
            continue

        # Flags
        if param in FLAGS["DEBUG"]:
            cfg.log_lvl = leng.LogLvls.DEBUG
        elif param in FLAGS["LOAD-EXTERNAL"]:
            cfg.pre_ld_ext_cmds = True
        elif param in FLAGS["STDOUT-ANSI"]:
            cfg.stdout_ansi = True
        elif param in FLAGS["STDERR-ANSI"]:
            cfg.stderr_ansi = True
        elif param in FLAGS["INFO"]:
            cfg.log_lvl = leng.LogLvls.INFO
        elif param in FLAGS["NO-WARNINGS"]:
            if cfg.log_lvl <= leng.LogLvls.WARN:
                cfg.log_lvl = leng.LogLvls.ERR
        elif param in FLAGS["HELP"]:
            ugen.write("\n".join(HELP_TXT).expandtabs(2))
            sys.exit(uerr.ERR_ALL_GOOD)
        # Options after this, hence check if value is present
        elif idx >= len(params) - 1:
            ugen.err_Q(f"Expected value for '{param}'")
            sys.exit(uerr.ERR_MP_EXPD_VAL_OPT)
        # Options
        elif param in OPTS["LINE-MODE"]:
            val = passed_params[idx + 1]
            if val not in ("emacs", "vi", "raw"):
                ugen.err_Q(f"Invalid value for '{param}': '{val}'")
                sys.exit(uerr.ERR_MP_INV_VAL)
            cfg.ln_mode = val
            idx += 1
        elif param in OPTS["DEBUG-TIME-UNIT"]:
            val = passed_params[idx + 1]
            if val == "ms":
                cfg.debug_time_expo = 6
            elif val == "us":
                cfg.debug_time_expo = 3
            elif val == "ns":
                cfg.debug_time_expo = 0
            elif val == "s":
                cfg.debug_time_expo = 9
            else:
                ugen.err_Q(f"Invalid value for '{param}': '{val}'")
                sys.exit(uerr.ERR_MP_INV_VAL)
            idx += 1
        # Not needed, but let it be there
        else:
            ugen.err_Q(f"Unknown parameter: '{param}'")
            sys.exit(uerr.ERR_MP_UNK_TOK)

        idx += 1

    args_len = len(args)
    if not (MIN_ARGS <= args_len <= MAX_ARGS):
        ugen.fatal_Q(
            f"Argument {"underflow" if MIN_ARGS < args_len else "overflow"}: {args_len} not in [{MIN_ARGS}, {MAX_ARGS}]",
            ret=uerr.ERR_INSUFF_ARGS if MIN_ARGS < args_len else uerr.ERR_UNEXPD_ARGS,
        )

    return cfg

def main() -> None:
    try:
        parsed = parse_argv(MainProgParsed(), sys.argv[1 :])
        with open(uconst.LOG_FL, "a") as log_fd:
            lgrs = leng.LgrVessel(
                leng.Lgr("lgr_c", "C", parsed.log_lvl, sys.stderr),
                leng.Lgr("lgr_q", "Q", parsed.log_lvl, sys.stderr),
                leng.Lgr("fl_lgr", "F", leng.LogLvls.CRIT, log_fd)
            )
        # Recommended not to put any debug, info or warning statements above
        # this, because even though those functions can handle loggers not
        # being initialised, they do not obey the log levels, because log
        # levels aren't available before the following line
        ugen.set_lgrs(lgrs)
        ugen.debug(ugen.fmt_d_stmt(
            src="log",
            lhs=f"opened log file {ugen.condense_pth(uconst.LOG_FL)}",
        ))
        cfg = cmgr.get_cfg()
        intrpr = ieng.Intrpr(
            cfg=cfg,
            pre_ld_ext_cmds=parsed.pre_ld_ext_cmds,
            stdout_ansi=parsed.stdout_ansi,
            stderr_ansi=parsed.stderr_ansi,
            debug_time_expo=parsed.debug_time_expo,
            log_lvl=parsed.log_lvl
        )
        ugen.info_Q(f"running from \"{uconst.RUN_PTH}\"")
        # No line mode option passed from command line
        if parsed.ln_mode == "default":
            if cfg.ln_mode != "raw":
                import readline as rl
                rl.parse_and_bind("tab: complete")
                if cfg.ln_mode == "vi":
                    rl.parse_and_bind("set editing-mode vi")
        # Line mode option passed from command line
        elif parsed.ln_mode != "raw":
            import readline as rl
            rl.parse_and_bind("tab: complete")
            if parsed.ln_mode == "vi":
                rl.parse_and_bind("set editing-mode vi")

    except Exception as e:
        tb.print_exc()
        ugen.fatal_Q(
            f"Interpreter init failed; {e.__class__.__name__}",
            uerr.ERR_UNK_FATAL,
            exc_txt=tb.format_exc(),
        )

    prompt_404_warned = False
    while True:
        try:
            try:
                prompt = intrpr.intrpr_vars["PROMPT"]
                prompt_404_warned = False
            except ugen.UnkVarErr:
                if not prompt_404_warned:
                    ugen.warn_Q("PROMPT not found; using default")
                prompt = uconst.Defaults.PROMPT
                prompt_404_warned = True
            raw_ln = input(intrpr.reslv_prompt(prompt))
            cmd_ret = intrpr.exec(raw_ln)
            intrpr.intrpr_vars["LAST_RET"] = cmd_ret
            ugen.debug(str(intrpr.intrpr_vars))

        # ^c on a built-in command
        except KeyboardInterrupt:
            intrpr.intrpr_vars["LAST_RET"] = uerr.ERR_KB_INTERR
            ugen.write("\n")

        # ^c on an external command
        except ugen.KeyboardInterruptWPrevileges as e:
            intrpr.intrpr_vars["LAST_RET"] = uerr.ERR_KB_INTERR
            os.kill(e.child_pid, sig.SIGKILL)
            ugen.write("\n")

        except EOFError:
            ugen.write("\nbye\n")
            sys.exit(uerr.ERR_ALL_GOOD)

        except Exception as e:
            ugen.fatal_Q(
                f"{e.__class__.__name__} in main interpreter loop\n{e}",
                uerr.ERR_UNK_FATAL,
                exc_txt=tb.format_exc()
            )


if __name__ == "__main__":
    main()
