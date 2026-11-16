#!/usr/bin/env -S python3 -BOO
import atexit
import dataclasses as dcs
import os
import signal as sig
import sys
import traceback as tb

from src.intrpr import cfg_mgr as cmgr
from src.intrpr import eng as ieng
from src.intrpr import prompt as iprom
from src.logger import eng as leng
from src.utils import consts as uconst
from src.utils import debug as udeb
from src.utils import err_codes as uerr
from src.utils import gen as ugen

if not sys.argv:
    ugen.fatal_Q(
        "What kind of sorcery is this? Why is the program run this way? (sys.argv is empty)",
        ret=uerr.RC.MP_SORCERY_EXIT,
    )
PROG = sys.argv[0]
# Nuitka overwrites sys.argv[0], and provides __compiled__ with original argv
if "__compiled__" in locals():
    PROG = __compiled__.original_argv0         # noqa: F821

VER = uconst.VER

MIN_ARGS = 0
MAX_ARGS = 1
USAGE = (f"{PROG} [FLAGS] [OPTS] [ARGS]",)
ARGS = ugen.Args({
    "FILE": ("Script to run",),
})
OPTS = ugen.Opts({
    "DEBUG-TIME-UNIT": (
        ("-t", "--debug-time-unit"),
        ("Unit for debugging time output", "Valid: 'ns', 'us', 'ms', 's'", "Default: 'ms'"),
    ),
    "LINE-MODE": (
        ("-m", "--line-mode"),
        ("Line mode to use for input", "Valid: 'emacs', 'vi', 'raw'", "Default: config-dependent"),
    ),
    "LOG-LEVEL": (
        ("-l", "--log-level"),
        (
            "Minimum log level for STDERR",
            "Valid: '[d]ebug', '[i]nfo', '[w]arn'",
            "       '[e]rr', '[c]rit', '[f]atal'",
            "Default: 'warn'",
        ),
    ),
    "FILE-LOG-LEVEL": (
        ("-f", "--file-log-level"),
        ("[NOT IMPLEMENTED] In progress...",),
    ),
})
FLAGS = ugen.Flags({
    "HELP": (("-h", "--help"), ("Display help text",)),
    "LOAD-EXTERNAL": (("-p", "--preload-external"), ("Load all external commands on startup",)),
    "STDERR-ANSI": (("-e", "--preserve-stderr-ANSI"), ("Preserve ANSI codes in STDERR redirects",)),
    "STDOUT-ANSI": (("-o", "--preserve-stdout-ANSI"), ("Preserve ANSI codes in STDOUT redirects",)),
})


def prn_help():
    # For calculating maximum header lengths
    all_args = ARGS.get_all_args()
    all_opts = [", ".join(i) for i in OPTS.get_all_opts()]
    all_flags = [", ".join(i) for i in FLAGS.get_all_flags()]

    # Maximum allowed length of header for in-line
    MAX_HEADER_COL_WID = 12
    # Compulsory padding between in-line header and description
    HEADER_DESC_PADDING = 4
    # Maximum length of all headers
    max_len = max((len(header) for header in all_args + all_opts + all_flags), default=0)
    # Left column (header column) fixed length
    left_col = min(MAX_HEADER_COL_WID, max_len)
    # Padding for in front of lines 2 to end for multi-line descriptions
    pad_for_newlines = f"\n\t{" " * (left_col + HEADER_DESC_PADDING)}"

    def _fmt_help_entry(header: str, desc: str) -> str:
        first_ln = desc[0] if desc else ""
        rest_lns = (pad_for_newlines + pad_for_newlines.join(desc[1 :])) if desc[1 :] else ""
        desc = first_ln + rest_lns
        # in-line header and description
        if len(header) <= left_col:
            header = header.ljust(left_col)
        # otherwise (description starts from next line)
        else:
            desc = pad_for_newlines + desc
        return f"\t{header}{" " * HEADER_DESC_PADDING}{desc}".expandtabs(2)

    to_prn = []

    to_prn.append("USAGE")
    to_prn.extend(f"\t{i}".expandtabs(2) for i in USAGE)

    to_prn.append("ARGUMENTS")
    for arg in ARGS:
        desc = ARGS.get(arg)
        to_prn.append(_fmt_help_entry(arg, desc))

    to_prn.append("OPTIONS")
    for opt_nm in OPTS:
        opts = OPTS.get_opts(opt_nm)
        header = ", ".join(opts)
        desc = OPTS.get_help(opt_nm)
        to_prn.append(_fmt_help_entry(header, desc))

    to_prn.append("FLAGS")
    for flag_nm in FLAGS:
        flags = FLAGS.get_flags(flag_nm)
        header = ", ".join(flags)
        desc = FLAGS.get_help(flag_nm)
        to_prn.append(_fmt_help_entry(header, desc))

    ugen.write("\n".join(to_prn) + "\n")


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
        if param == "-" or not param.startswith("-") or not parse_opts_flags:
            args.append(param)
            idx += 1
            continue
        if param == "--":
            parse_opts_flags = False
            idx += 1
            continue
        if param not in OPTS and param not in FLAGS:
            if [i for i in param[1 :] if f"-{i}" not in OPTS and f"-{i}" not in FLAGS]:
                ugen.fatal_Q(f"Unknown token: '{param}'", ret=uerr.RC.MP_UNK_TOK)
            params[idx : idx + 1] = [f"-{i}" for i in param[1 :]]
            continue

        # Flags
        if param in FLAGS.get_flags("HELP"):
            prn_help()
            sys.exit(uerr.RC.ALL_GOOD)
        elif param in FLAGS.get_flags("LOAD-EXTERNAL"):
            cfg.pre_ld_ext_cmds = True
        elif param in FLAGS.get_flags("STDOUT-ANSI"):
            cfg.stdout_ansi = True
        elif param in FLAGS.get_flags("STDERR-ANSI"):
            cfg.stderr_ansi = True
        # Options after this, hence check if value is present
        elif idx >= len(params) - 1:
            ugen.err_Q(f"Expected value for '{param}'")
            sys.exit(uerr.RC.MP_EXPD_VAL_OPT)
        # Options
        elif param in OPTS.get_opts("LINE-MODE"):
            val = params[idx + 1]
            if val not in ("emacs", "vi", "raw"):
                ugen.err_Q(f"Invalid value for {param!r}: {val!r}")
                sys.exit(uerr.RC.MP_INV_VAL)
            cfg.ln_mode = val
            idx += 1
        elif param in OPTS.get_opts("DEBUG-TIME-UNIT"):
            val = params[idx + 1]
            if val == "ms":
                cfg.debug_time_expo = 6
            elif val == "us":
                cfg.debug_time_expo = 3
            elif val == "ns":
                cfg.debug_time_expo = 0
            elif val == "s":
                cfg.debug_time_expo = 9
            else:
                ugen.err_Q(f"Invalid value for {param!r}: {val!r}")
                sys.exit(uerr.RC.MP_INV_VAL)
            idx += 1
        elif param in OPTS.get_opts("LOG-LEVEL"):
            val = params[idx + 1]
            if val in ("d", "debug"):
                cfg.log_lvl = leng.LogLvls.DEBUG
            elif val in ("i", "info"):
                cfg.log_lvl = leng.LogLvls.INFO
            elif val in ("w", "warn"):
                cfg.log_lvl = leng.LogLvls.WARN
            elif val in ("e", "err"):
                cfg.log_lvl = leng.LogLvls.ERR
            elif val in ("c", "crit"):
                cfg.log_lvl = leng.LogLvls.CRIT
            elif val in ("f", "fatal"):
                cfg.log_lvl = leng.LogLvls.FATAL
            else:
                ugen.err_Q(f"Invalid value for {param!r}: {val!r}")
                sys.exit(uerr.RC.MP_INV_VAL)
            idx += 1
        # Not needed, but let it be there
        else:
            ugen.err_Q(f"Unknown parameter: '{param}'")
            sys.exit(uerr.RC.MP_UNK_TOK)

        idx += 1

    args_len = len(args)
    if not (MIN_ARGS <= args_len <= MAX_ARGS):
        ugen.fatal_Q(
            f"Argument {"underflow" if args_len < MIN_ARGS else "overflow"}: {args_len} not in [{MIN_ARGS}, {MAX_ARGS}]",
            ret=uerr.RC.INSUFF_ARGS if args_len < MIN_ARGS else uerr.RC.UNEXPD_ARGS,
        )

    if len(args) >= 1:
        cfg.fl = args[0]

    return cfg

def main() -> None:
    try:
        parsed = parse_argv(MainProgParsed(), sys.argv[1 :])
        log_fd =  open(uconst.LOG_FL, "a")
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
        intrpr_proc_pid = os.getpid()
        atexit.register(lambda: intrpr.shm.unlink() if os.getpid() == intrpr_proc_pid else None)

        ugen.info_Q(ugen.fmt_i_stmt("running from", uconst.RUN_PTH))
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
        ugen.fatal_Q(
            f"Interpreter init failed; {e.__class__.__name__}",
            uerr.RC.UNK_FATAL,
            exc_txt=tb.format_exc(),
        )

    if parsed.fl is not None:
        data = None
        try:
            with open(parsed.fl) as f:
                data = f.read()
        except FileNotFoundError:
            ugen.fatal_Q(f"No such file: {parsed.fl!r}", ret=uerr.RC.MP_FL_404)
        except PermissionError:
            ugen.fatal_Q(f"Access denied: {parsed.fl!r}", ret=uerr.RC.MP_PERM_DENIED)
        except IsADirectoryError:
            ugen.fatal_Q(f"Is a directory: {parsed.fl!r}", ret=uerr.RC.MP_IS_A_DIR)
        except OSError as e:
            ugen.fatal_Q(f"OS error; {e.strerror}: {parsed.fl!r}", ret=uerr.RC.MP_OS_ERR)
        except UnicodeDecodeError:
            ugen.fatal_Q(f"Does not appear to contain text: {parsed.fl!r}", ret=uerr.RC.MP_DECODE_ERR)
        except Exception as e:
            ugen.fatal_Q(
                f"Unexpected exception {e.__class__.__name__} when reading file {parsed.fl!r}: {e}",
                ret=uerr.RC.MP_UNHDLD_EXC,
                exc_txt=tb.format_exc(),
            )

        try:
            if data is None:
                ugen.fatal_Q(f"Could not get file contents: {parsed.fl!r}")
            for ln in data.splitlines():
                cmd_ret = intrpr.exec(ln)
                intrpr.intrpr_vars["LAST_RET"] = cmd_ret
                ugen.debug_Q(ugen.fmt_d_stmt("gen", "intrpr_vars", str(intrpr.intrpr_vars)))
        except KeyboardInterrupt:
            sys.exit(uerr.RC.MP_KB_INTERR)
        except EOFError:
            sys.exit(uerr.RC.MP_EOF)
        except Exception as e:
            sys.exit(uerr.RC.MP_UNHDLD_EXC)

    else:
        # Interactive session
        prompt_404_warned = False
        os.chdir(udeb.TMP_DIR)
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
                raw_ln = input(iprom.reslv_prompt(intrpr, prompt))
                cmd_ret = intrpr.exec(raw_ln)
                intrpr.intrpr_vars["LAST_RET"] = cmd_ret
                ugen.debug_Q(ugen.fmt_d_stmt("gen", "intrpr vars", str(intrpr.intrpr_vars)))

            except KeyboardInterrupt:
                intrpr.intrpr_vars["LAST_RET"] = uerr.RC.KB_INTERR
                ugen.write("\n")

            except EOFError:
                ugen.write("\nbye\n")
                sys.exit(uerr.RC.ALL_GOOD)

            except Exception as e:
                ugen.fatal_Q(
                    f"Fatal exception {e.__class__.__name__} in interpreter loop: {e}",
                    ret=uerr.RC.UNK_FATAL,
                    exc_txt=tb.format_exc()
                )


if __name__ == "__main__":
    main()
