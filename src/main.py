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
    called_nm = "[main]"
else:
    called_nm = sys.argv[0]
    # Nuitka overwrites sys.argv[0]
    if "__compiled__" in locals():
        called_nm = __compiled__.original_argv0

MIN_ARGS = 0
MAX_ARGS = 1
OPTS = {
    "-l", "--line-mode",
    "-t", "--debug-time-unit",
}
FLAGS = {
    "-d", "--debug",
    "-e", "--preserve-stderr-ANSI",
    "-h", "--help",
    "-i", "--info",
    "-o", "--preserve-stdout-ANSI",
    "-p", "--preload-external",
    "-W", "--no-warnings",
}

# TODO: Update the help string
HELP_TXT = (
    "USAGE",
    f"\t{called_nm} [flag ...] [opt] [fl]",
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
    "\t-e, --load-external",
    "\t            Load all external commands on startup",
    "\t-h, --help  Display help text",
    "\t-i, --info  Show info messages",
    "\t-l, ",
    "\t-pe, --preserve-ANSI-stderr",
    "\t            Preserve ANSI codes in STDERR redirects",
    "\t-po, --preserve-ANSI-stdout",
    "\t            Preserve ANSI codes in STDOUT redirects",
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

    while idx < len(params):
        param = params[idx]
        if not (param.startswith("-") and parse_opts_flags):
            args.append(param)
            continue
        if param == "--":
            parse_opts_flags = False
            continue
        if param not in (*FLAGS, *OPTS):
            if [i for i in param[1 :] if f"-{i}" not in FLAGS]:
                ugen.err_Q(f"Unknown parameter: '{param}'")
                sys.exit(uerr.ERR_MP_UNK_TOK)
            params[idx : idx + 1] = list(param[1 :])
            continue

        # Flags
        if param in ("-d", "--debug"):
            cfg.log_lvl = leng.LogLvls.DEBUG
        elif param in ("-e", "--load-external"):
            cfg.pre_ld_ext_cmds = True
        elif param in ("-o", "--preserve-ANSI-stdout"):
            cfg.stdout_ansi = True
        elif param in ("-e", "--preserve-ANSI-stderr"):
            cfg.stderr_ansi = True
        elif param in ("-i", "--info"):
            cfg.log_lvl = leng.LogLvls.INFO
        elif param in ("-W", "--no-warnings"):
            if cfg.log_lvl <= leng.LogLvls.WARN:
                cfg.log_lvl = leng.LogLvls.ERR
        elif param in ("-h", "--help"):
            ugen.write("\n".join(HELP_TXT).expandtabs(2))
            sys.exit(uerr.ERR_ALL_GOOD)
        # Options after this, hence check if value is present
        elif idx >= len(params) - 1:
            ugen.err_Q(f"Expected value for '{param}'")
            sys.exit(uerr.ERR_MP_EXPD_VAL_OPT)
        # Options
        elif param in ("-l", "--line-mode"):
            val = passed_params[idx + 1]
            if val not in ("emacs", "vi", "raw"):
                ugen.err_Q(f"Invalid value for '{param}': '{val}'")
                sys.exit(uerr.ERR_MP_INV_VAL)
            cfg.ln_mode = val
            idx += 1
        elif param in ("-t", "--debug-time-unit"):
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
        log_fd = open(uconst.LOG_FL, "a")
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
