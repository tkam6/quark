import atexit
import errno
import io
import logging as lg
import multiprocessing as mp
import multiprocessing.shared_memory as mpshm
import os
import os.path as ospth
import pickle as pi
import platform as pf
import pwd
import re
import select as sel
import signal as sig
import struct as st
import sys
import time
import traceback as tb
import typing as ty

from src.intrpr import cfg_mgr as cmgr
from src.intrpr import cmd_reslvr as icrsr
from src.intrpr import internals as iint
from src.parser import ast_nodes as past
from src.parser import eng as peng
from src.utils import consts as uconst
from src.utils import debug as udeb
from src.utils import err_codes as uerr
from src.utils import gen as ugen

if ty.TYPE_CHECKING:
    from src.parser import internals as pint

TH_TokGrp = tuple[list[str], "pint.SpChr"]
TH_CmdFn = ty.Callable[[ugen.CmdData], int]
TH_GetCmdRes = tuple[TH_CmdFn, ugen.CmdSpec]


class Intrpr:
    def __init__(
            self,
            cfg: cmgr.Cfg,
            pre_ld_ext_cmds: bool,
            stdout_ansi: bool,
            stderr_ansi: bool,
            debug_time_expo: int,
            log_lvl: int
            ) -> None:
        self.ext_cached_cmds: dict[str, iint.CmdCacheEntry]

        # Interpreter initialisation time start
        _t_intrpr_init = time.perf_counter_ns()

        ugen.warn_Q("Exercise caution when running untrusted commands")

        self.GET_CMD_ERR_MSG_MAP = {
            uerr.ERR_BAD_CMD: "Bad command",
            uerr.ERR_INV_CMD: "Invalid command file",
            uerr.ERR_NO_CMD_FN: "Missing command function",
            uerr.ERR_NO_CMD_SPEC: "Missing command spec",
            uerr.ERR_NO_HELP_OBJ: "Missing help object",
            uerr.ERR_UNCALLABLE_CMD_FN: "Uncallable command function",
            uerr.ERR_INV_NUM_PARAMS: "Bad function argument count",
            uerr.ERR_INV_CMD_SPEC: "Bad command spec",
            uerr.ERR_INV_HELP_OBJ: "Bad help oject",
            uerr.ERR_RECUR_ERR: "Recursion limit exceeded",
            uerr.ERR_CMD_SYN_ERR: "Syntax error",
            uerr.ERR_CANT_LD_CMD_MOD: "Load failed"
        }
        self.usr_dir = os.path.expanduser("~")
        self.uid = str(os.getuid())
        self.usernm = pwd.getpwuid(int(self.uid)).pw_name
        self.is_usr_root = (self.uid == "0")

        # See src.intrpr.internals.EnvTbl for memory layout
        # Memory for total number of items = 8B
        # Memory for write index           = 64B
        # Maximum number of entries        = 100
        # Memory per variable entry        = (8+8+128+8048)B = 8192B = 8KiB
        #     Length of key   = 8B
        #     Length of value = 8B
        #     Key             = 128B
        #     Value           = 8048B
        self.SHM_SZ = 819272
        self.shm = mpshm.SharedMemory(
            create=True,
            track=True,
            size=self.SHM_SZ
        )
        self.lock = mp.RLock()
        atexit.register(self.shm.unlink)

        self.ext_cached_cmds = {}
        self.cfg = cfg
        self.stdout_ansi = stdout_ansi
        self.stderr_ansi = stderr_ansi
        self.debug_time_expo = debug_time_expo
        self.log_lvl = log_lvl
        self.intrpr_vars = iint.IntrprTbl()
        self.env_vars = iint.EnvTbl(self.shm, self.lock)
        self.parser = peng.Parser()
        self.cmd_reslvr = icrsr.CmdReslvr(
            self.ext_cached_cmds,
            self.debug_time_expo
        )
        self._last_bad_prompt_obj = None

        self.intrpr_vars["_USR_DIR_"] = str(self.usr_dir)
        self.intrpr_vars["_PREV_CWD_"] = os.getcwd()
        self.intrpr_vars["LAST_RET"] = uerr.ERR_ALL_GOOD

        try:
            os.chdir(udeb.TMP_DIR)
        except FileNotFoundError:
            pass
        except PermissionError:
            pass
        except OSError:
            pass

        self.use_cfg()

        if pre_ld_ext_cmds:
            # DEBUG: Pre-load external modules time start
            _t_pre_ld = time.perf_counter_ns()
            self.ld_all_ext_mods()
            # DEBUG: Pre-load external module time end
            _t_pre_ld = time.perf_counter_ns() - _t_pre_ld
            ugen.debug_Q(
                ugen.fmt_d_stmt(
                    "time",
                    "tot_pre_ld_ext",
                    self.fmt_t_ns(_t_pre_ld)
                )
            )

        # Interpreter initialisation time end
        _t_intrpr_init = time.perf_counter_ns() - _t_intrpr_init

        ugen.debug_Q(
            ugen.fmt_d_stmt(
                "time",
                "tot_init_intrpr",
                self.fmt_t_ns(_t_intrpr_init)
            )
        )

    def fmt_t_ns(self, ns: int) -> str:
        return ugen.fmt_t_ns(self.debug_time_expo, ns)

    def reslv_prompt_var(
        self,
        prompt: ty.Callable[[iint.IntrprTbl], ty.Any] | str
    ) -> str:
        dflt_prompt = uconst.Defaults.PROMPT(self.intrpr_vars)

        if isinstance(prompt, str):
            prompt_str = prompt
        elif callable(prompt):
            try:
                prompt_str = prompt(self.intrpr_vars)
            except Exception as e:
                ugen.crit_Q(f"Errant prompt function; {e.__class__.__name__}")
                prompt_str = dflt_prompt
            if not isinstance(prompt_str, str):
                ugen.crit_Q(
                    f"Expected 'str' from prompt function, got '{type(prompt_str).__name__}'"
                )
                prompt_str = dflt_prompt
        else:
            ugen.crit_Q(f"Invalid prompt type: '{type(prompt).__name__}'")
            prompt_str = dflt_prompt

        return prompt_str

    def reslv_prompt(
        self,
        prompt_obj: ty.Callable[[iint.IntrprTbl], ty.Any] | str | None
    ) -> str:
        # Pretty bad design, I guess, handling the None case for variable
        # prompt in this method, but I don't want to clutter up the main file
        if prompt_obj is None:
            prompt_obj = uconst.Defaults.PROMPT

        prompt = self.reslv_prompt_var(prompt_obj)
        len_prompt = len(prompt)
        final_prompt = ""
        skip = 0

        for i, char in enumerate(prompt):
            if skip:
                skip -= 1
                continue
            if char != "!":
                final_prompt += char
                continue
            # ! at the end of prompt
            if i == len_prompt - 1:
                # Issue warning only once
                if self._last_bad_prompt_obj != prompt_obj:
                    ugen.warn_Q(
                        "Lone '!' in prompt variable; falling back to default prompt",
                    )
                    self._last_bad_prompt_obj = prompt_obj
                return self.reslv_prompt(uconst.Defaults.PROMPT)

            nxt_chr = prompt[i + 1]

            # Condensed path
            if nxt_chr == "p":
                cwd_conden = re.sub(
                    f"^{re.escape(str(self.usr_dir))}",
                    "~",
                    os.getcwd()
                )
                final_prompt += cwd_conden
                skip += 1
                continue
            # Condensed path with slashes at the end for all directories except
            # the root and user directory
            elif nxt_chr == "P":
                cwd_conden = re.sub(
                    f"^{self.usr_dir}",
                    "~",
                    os.getcwd()
                )
                final_prompt += cwd_conden
                if not (cwd_conden == "~" or cwd_conden == "/"):
                    final_prompt += "/"
                skip += 1
                continue
            # Expanded path
            elif nxt_chr == "e":
                cwd = os.getcwd()
                final_prompt += cwd
                skip += 1
                continue
            # Username
            elif nxt_chr == "u":
                final_prompt += self.usernm
                skip += 1
                continue
            elif nxt_chr == "U":
                final_prompt += self.uid
                skip += 1
                continue
            # Hostname
            elif nxt_chr == "h":
                final_prompt += pf.node()
                skip += 1
                continue
            # Quark version
            elif nxt_chr == "v":
                final_prompt += uconst.VER
                skip += 1
                continue
            # Elevation symbols (how else can I describe this?)
            elif nxt_chr == "$":
                if self.is_usr_root:
                    final_prompt += "%"
                else:
                    final_prompt += "$"
                skip += 1
                continue
            elif nxt_chr == "?":
                final_prompt += str(self.intrpr_vars["LAST_RET"])
                skip += 1
                continue
            # Literal '!'
            elif nxt_chr == "!":
                final_prompt += "!"
                skip += 1
                continue
            else:
                # Issue warning only once
                if self._last_bad_prompt_obj != prompt_obj:
                    ugen.warn_Q(
                        f"Invalid prompt substitution symbol: '!{nxt_chr}'; falling back to default prompt"
                    )
                    self._last_bad_prompt_obj = prompt_obj
                return self.reslv_prompt(uconst.Defaults.PROMPT)

        return final_prompt

    def use_cfg(self) -> None:
        self.intrpr_vars.set("PROMPT", self.cfg.prompt, protected=True)
        self.intrpr_vars.set("ALIASES", self.cfg.aliases, protected=True)
        expansions = {
            "@bin" : uconst.PY_PTH,
            "@run": uconst.RUN_PTH
        }
        pths = []
        for pth in self.cfg.pth:
            matches = [ex for ex in expansions if pth.startswith(ex)]
            if matches:
                pth = re.sub(f"^{matches[0]}", expansions[matches[0]], pth)
            pths.append(os.path.abspath(ospth.realpath(ospth.expanduser(pth))))
        self.intrpr_vars.set("PTH", tuple(pths), protected=True)

    def ld_all_ext_mods(self) -> None:
        pths = self.intrpr_vars["PTH"]
        for pth in pths:
            pth = ospth.realpath(ospth.expanduser(pth))
            try:
                for i in os.scandir(pth):
                    if ospth.isdir(i):
                        continue
                    if not i.name.endswith(".py"):
                        continue
                    if i.name == "__init__.py":
                        continue
                    tmp = self.cmd_reslvr.get_ext_cmd(
                        ospth.splitext(i.name)[0],
                        ext_cached_cmds=self.ext_cached_cmds,
                        pths=pths
                    )
                    if isinstance(tmp, int):
                        continue
                    ugen.info_Q(f"loaded {i.path}")
            except FileNotFoundError:
                ugen.warn_Q(f"No such directory: \"{pth}\"")
            except NotADirectoryError:
                ugen.warn_Q(f"Not a directory: \"{pth}\"")
            except PermissionError:
                ugen.warn_Q(f"Access denied; cannot load modules: \"{pth}\"")
            except OSError as e:
                ugen.warn_Q(f"OS error; {e.strerror}")

    def get_cmd(
        self,
        cmd_nm: str,
        ext_cached_cmds: dict[str, iint.CmdCacheEntry],
        cmd_reslvr: icrsr.CmdReslvr,
        intrpr_vars: iint.IntrprTbl
    ) -> tuple[
        ty.Callable[[ugen.CmdData], int],
        ugen.CmdSpec,
        str
    ] | int:
        builtin_cmd = self.cmd_reslvr.get_builtin_cmd(cmd_nm)
        if isinstance(builtin_cmd, tuple):
            return (*builtin_cmd, "built-in")

        ext_cmd = self.cmd_reslvr.get_ext_cmd(
            cmd_nm,
            intrpr_vars["PTH"],
            ext_cached_cmds,
        )
        if isinstance(ext_cmd, int):
            return ext_cmd
        return (*ext_cmd, "external")

    def classi_params(
        self,
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
                # Then options
                elif param_val in cmd_spec.opts:
                    if idx >= params_len - 1:
                        ugen.err(
                            f"Expected value for option '{param_val}'",
                            nm=cmd_nm,
                        )
                        return uerr.ERR_EXPD_VAL_OPT
                    opts[param_val] = params[idx + 1].val
                    skip += 1
                # Invalid long-form option/flag
                else:
                    ugen.err(f"Invalid option/flag: '{param_val}'", nm=cmd_nm)
                    return uerr.ERR_INV_OPTS_FLAGS
                continue

            # SHORT-FORM OPTIONS AND FLAGS, OR COMBINED SHORT-FORM FLAGS
            if (
                param_val.startswith("-")
                and not param_val.startswith("--")
                and not param.escd_hyp
            ):
                if param_val in cmd_spec.flags:
                    flags.append(param_val)
                elif param_val in cmd_spec.opts:
                    if idx >= params_len - 1:
                        ugen.err(
                            f"Expected value for option '{param_val}'",
                            nm=cmd_nm
                        )
                        return uerr.ERR_EXPD_VAL_OPT
                    opts[param_val] = params[idx + 1].val
                    skip += 1
                else:
                    # Lone '-'
                    if not param_val[1 :]:
                        ugen.err(
                            f"Invalid option/flag: '{param_val}'",
                            nm=cmd_nm,
                        )
                        return uerr.ERR_INV_OPTS_FLAGS
                    # Combined short flags
                    for i in param_val[1 :]:
                        if "-" + i in cmd_spec.flags:
                            flags.append("-" + i)
                            continue
                        ugen.err(
                            f"Invalid option/flag: '{param_val}'",
                            nm=cmd_nm,
                        )
                        return uerr.ERR_INV_OPTS_FLAGS
                continue

            # ARGUMENTS
            arg_cnt += 1
            if arg_cnt > cmd_spec.max_args:
                ugen.err(
                    f"Argument overflow; {arg_cnt} not in [{cmd_spec.min_args}, {cmd_spec.max_args}]",
                    nm=cmd_nm,
                )
                return uerr.ERR_UNEXPD_ARGS
            args.append(param_val)

        if arg_cnt < cmd_spec.min_args:
            ugen.err(
                f"Argument underflow; {arg_cnt} not in [{cmd_spec.min_args}, {cmd_spec.max_args}]",
                nm=cmd_nm,
            )
            return uerr.ERR_INSUFF_ARGS

        # Horrendous
        sub_cmd = None
        if cmd_spec.parse_sub_cmds:
            sub_cmd = sub_cmd if args == [] else args.pop(0)
            arg_cnt = len(args)
            # Subcommand is not present in the command spec
            if sub_cmd not in cmd_spec.sub_cmds:
                if sub_cmd is None:
                    ugen.err("Expected subcommand", nm=cmd_nm)
                    return uerr.ERR_EXPD_SUB_CMD
                else:
                    ugen.err(f"Invalid subcommand: '{sub_cmd}'", nm=cmd_nm)
                    return uerr.ERR_INV_SUB_CMD
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
                return uerr.ERR_INSUFF_ARGS
            elif arg_cnt > upper_lt:
                ugen.err(
                    (
                        "Unexpected arguments"
                        + (f" ({sub_cmd})" if sub_cmd is not None else "")
                        + f"; {arg_cnt} not in [{lower_lt}, {upper_lt}]"
                    ),
                    nm=cmd_nm,
                )
                return uerr.ERR_UNEXPD_ARGS

        return (sub_cmd, tuple(args), opts, tuple(flags))

    def rd_from_fd(self, fd: int, n: int) -> bytes:
        chunks = []
        total = 0
        while total < n:
            chunk = os.read(fd, n - total)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        return b"".join(chunks)

    def write_to_fd(self, fd: int, data: str) -> None:
        len_data = len(data)
        total = 0
        while total < len_data:
            total += os.write(fd, data[total :])

    def loop_set_lgr_streams(
        self,
        chk_if: io.TextIOBase,
        set_to: io.TextIOBase
    ) -> None:
        for lgr in lg.Logger.manager.loggerDict.values():
            lgr: lg.Logger
            if isinstance(lgr, lg.PlaceHolder):
                continue
            for hdlr in lgr.handlers:
                if hdlr.stream is chk_if:
                    hdlr.stream = set_to

    def cmd_resln(self, cmd_nm: str) -> iint.CmdReslnRes | None | int:
        # DEBUG: Command resolution time start
        _t_cmd_resln = time.perf_counter_ns()

        err_code = uerr.ERR_ALL_GOOD
        get_cmd_res = self.get_cmd(
            cmd_nm,
            self.ext_cached_cmds,
            self.cmd_reslvr,
            self.intrpr_vars
        )
        if cmd_nm == "snoo":
            snoo_obj = iint.Snoo()
            return iint.CmdReslnRes(snoo_obj.run, snoo_obj.CMD_SPEC, "built-in")
        if isinstance(get_cmd_res, int):
            # If command name is in alias list, then don't print an error
            # message because aliases are handled elsewhere
            if cmd_nm in self.intrpr_vars["ALIASES"]:
                return get_cmd_res
            # Write error message to current STDERR
            err_msg = self.GET_CMD_ERR_MSG_MAP.get(
                get_cmd_res,
                "missing_err_msg",
            )
            err_code = err_code or get_cmd_res
            ugen.err_Q(f"{err_msg}: '{cmd_nm}'")
            return get_cmd_res

        # DEBUG: Command resolution time end
        _t_cmd_resln = time.perf_counter_ns() - _t_cmd_resln
        ugen.debug_Q(
            ugen.fmt_d_stmt(
                "time",
                "cmd_reslv",
                self.fmt_t_ns(_t_cmd_resln)
            )
        )

        return iint.CmdReslnRes(*get_cmd_res)

    def child_proc(
        self,
        cmd_fn: TH_CmdFn,
        data: ugen.CmdData,
        wout: int,
        werr: int,
        wother: int,
        stdout_obj: io.TextIOBase,
        stderr_obj: io.TextIOBase,
    ) -> ty.NoReturn:
        os.dup2(wout, 1)  # Redirect STDOUT to write end of pipe wout
        os.dup2(werr, 2)  # Redirect STDERR to write end of pipe werr
        os.close(wout)
        os.close(werr)
        excep = None
        try:
            cmd_ret = self.rn_cmd_fn(cmd_fn, data)
            exceps_raised = False
        except Exception as e:
            excep = e
            exceps_raised = True
            if isinstance(e, RecursionError):
                cmd_ret = uerr.ERR_RECUR_ERR
            else:
                cmd_ret = uerr.ERR_CMD_RNTIME_ERR

        if not isinstance(cmd_ret, int):
            ugen.crit_Q("Last command returned non-integer")
            cmd_ret = uerr.ERR_CMD_RETD_NON_INT
        # 2 ** 31 = 2147483648
        elif not -2147483648 <= cmd_ret < 2147483648:
            ugen.crit_Q(
                f"Command return value exceeds 32-bit signed integer limit: {cmd_ret}"
            )
            cmd_ret = uerr.ERR_RET_INT_TOO_LARGE
        # Pass data:
        # 1. Command return code
        # 2. If any exceptions were raised
        # Case: If any exceptions were raised:
        #       3. Length of the traceback string
        #       4. The traceback string
        os.write(wother, st.pack("!i", cmd_ret))
        os.write(wother, st.pack("!?", exceps_raised))
        if exceps_raised:
            pickled_excep = pi.dumps(iint.ExcepWNoLoss(excep))
            os.write(wother, st.pack("!Q", len(pickled_excep)))
            self.write_to_fd(wother, pickled_excep)
        os.close(wother)
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)

    def rd_and_unpack(self, fd: int, fmt_str: str, expd_bytes: int) -> ty.Any:
        packed_obj = self.rd_from_fd(fd, expd_bytes)
        try:
            return st.unpack(fmt_str, packed_obj)[0]
        except st.error:
            ugen.crit_Q(f"Expected {expd_bytes}-byte unpack ({fmt_str})")
            return

    def retrieve_excep(self, fd: int) -> str | None:
        pickled_excep_len = self.rd_and_unpack(fd, "!Q", 8)
        if not isinstance(pickled_excep_len, int):
            return
        pickled_excep = self.rd_from_fd(fd, pickled_excep_len)
        if isinstance(pickled_excep, bytes):
            return pi.loads(pickled_excep)
        return None

    def stream_data(
        self,
        fds_w_disp_objs: dict[int, io.TextIOBase],
        chunk_sz: int
    ) -> None:
        poller = sel.poll()
        open_fds = set(fds_w_disp_objs.keys())
        for fd in fds_w_disp_objs:
            poller.register(fd, sel.POLLHUP | sel.POLLIN)
        while open_fds:
            evts = poller.poll()
            for fd, evt in evts:
                # Event when pipe has data
                if evt & sel.POLLIN:
                    chunk = os.read(fd, chunk_sz)
                    if not chunk:
                        continue
                    fds_w_disp_objs[fd].write(chunk.decode())
                # Pipe close event
                if evt & sel.POLLHUP:
                    # I've seen KeyError at this place once... don't know why,
                    # but I'm adding in checks to make sure the program doesn't
                    # crash
                    poller.unregister(fd)
                    open_fds.remove(fd) if fd in open_fds else None

    def exec_cmd_fn(
        self,
        cmd_fn: TH_CmdFn,
        cmd_src: str,
        data: ugen.CmdData,
        stdout_obj: io.TextIOBase,
        stderr_obj: io.TextIOBase
    ) -> iint.CmdCompdObj:
        err_code = uerr.ERR_ALL_GOOD
        pid = 0

        # It's assumed that cmd_src can only be one of two values, "external"
        # and "built-in"
        if cmd_src == "external":
            ugen.debug("resolved to external command")
            try:
                # Two pipes 1 and 2 for output and return code
                rout, wout = os.pipe()
                rerr, werr = os.pipe()
                rother, wother = os.pipe()
                pid = os.fork()
            except OSError as e:
                if e.errno == errno.EMFILE:
                    ugen.crit_Q(
                        f"Too many open files; command '{data.cmd_nm}'",
                        exc_txt=tb.format_exc()
                    )
                    err_code = uerr.ERR_TOO_MANY_OPEN_FLS
                    return iint.CmdCompdObj(err_code=err_code)
                raise e
            # Child process; run in forked process
            if pid == 0:
                os.close(rout)
                os.close(rother)
                self.child_proc(
                    cmd_fn,
                    data,
                    wout,
                    werr,
                    wother,
                    stdout_obj,
                    stderr_obj,
                )
            # Some issue, can't fork
            elif pid < 0:
                ugen.crit_Q(
                    "Failed to fork process; try re-running the command"
                )
                err_code = uerr.ERR_CANT_FORK_PROC
            # Parent process
            else:
                try:
                    # Do NOT rely on child process exit codes, because Linux only
                    # supports 8-bit uints; child process always has an exit code 0
                    os.close(wout)
                    os.close(werr)
                    os.close(wother)
                    # Stream STDOUT and STDERR of child from pipe
                    self.stream_data({rout: stdout_obj, rerr: stderr_obj}, 4096)
                    os.close(rout)
                    os.close(rerr)
                    # 4 bytes for command return code
                    ret_code = self.rd_and_unpack(rother, "!i", 4)
                    if ret_code is None:
                        ret_code = uerr.ERR_UNPACK_FAIL
                    # 1 byte for data on if any exceptions were raised
                    exceps_raised = self.rd_and_unpack(rother, "!?", 1)
                    if exceps_raised is None:
                        ret_code = uerr.ERR_UNPACK_FAIL
                    elif exceps_raised:
                        excep_wrap = self.retrieve_excep(rother)
                        excep_nm = excep_wrap.e.__class__.__name__
                        excep_str = str(excep_wrap.e)
                        tb_msg = "".join(excep_wrap.exc_txt)
                        os.kill(pid, sig.SIGKILL)
                        if isinstance(excep_wrap.e, RecursionError):
                            ugen.crit_Q(
                                f"Recursion depth exceeded; command '{data.cmd_nm}'",
                                exc_txt=(f"Recursion depth exceeded; command '{data.cmd_nm}'\n"
                                         f"{tb_msg}"  # There's already a newline at the end
                                         f"{excep_nm}: {excep_str}")
                            )
                        else:
                            ugen.crit_Q(
                                f"Uncaught exception in external command '{data.cmd_nm}': {excep_nm}",
                                exc_txt=(f"Uncaught exception in external command '{data.cmd_nm}'\n"
                                         f"{tb_msg}"  # There's already a newline at the end
                                         f"{excep_nm}: {excep_str}")
                            )
                    os.close(rother)
                    # To prevent zombie (defunct) processes
                    os.wait()
                    # _, status = os.wait()
                    # exit_status = os.WEXITSTATUS(status)
                    err_code = err_code or ret_code
                except KeyboardInterrupt as e:
                    if pid == 0:
                        raise e
                    elif pid > 0:
                        raise ugen.KeyboardInterruptWPrevileges(e, pid)

        # Built-in command; run in same process as interpreter
        elif cmd_src == "built-in":
            ugen.debug("resolved to built-in command")
            try:
                cmd_ret = self.rn_cmd_fn(cmd_fn, data)
            except RecursionError:
                cmd_ret = uerr.ERR_RECUR_ERR
                ugen.crit_Q(
                    f"Recursion depth exceeded; command '{data.cmd_nm}'",
                    exc_txt=(f"Recursion depth exceeded; command '{data.cmd_nm}'\n"
                             f"{tb.format_exc()}")
                )
            except Exception as e:
                cmd_ret = uerr.ERR_CMD_RNTIME_ERR
                ugen.crit_Q(
                    f"Uncaught exception in built-in command '{data.cmd_nm}': {e.__class__.__name__}",
                    exc_txt=(f"Uncaught exception in built-in command '{data.cmd_nm}'\n"
                             f"{tb.format_exc()}")
                )
            err_code = err_code or cmd_ret

        return iint.CmdCompdObj(err_code=err_code)

    def exec_cmd(
        self,
        cmd_nm: str,
        cmd_fn: TH_CmdFn,
        cmd_spec: ugen.CmdSpec,
        cmd_src: str,
        params: list[past.Param],
        is_tty: bool,
        stdin: str,
        stdout_obj: io.TextIOBase,
        stderr_obj: io.TextIOBase
    ):
        # Classify parameters into arguments, options and flags
        tmp = self.classi_params(cmd_nm, params, cmd_spec)
        if isinstance(tmp, int):
            return iint.CmdCompdObj(tmp)
        sub_cmd, args, opts, flags = tmp

        try:
            term_sz = os.get_terminal_size()
        except OSError:
            term_sz = None
        if cmd_src == "built-in":
            intrpr_vars_cp = self.intrpr_vars
        else:
            intrpr_vars_cp = self.intrpr_vars.crt_self_cp()

        data = ugen.CmdData(
            cmd_nm=cmd_nm,
            sub_cmd=sub_cmd,
            args=tuple(args),
            opts=opts,
            flags=tuple(flags),
            cmd_reslvr=self.cmd_reslvr,
            intrpr_vars=intrpr_vars_cp,
            env_vars=self.env_vars,
            ext_cached_cmds=self.ext_cached_cmds,
            term_sz=term_sz,
            is_tty=is_tty,
            stdin=stdin,
            exec_fn=self.exec,
        )
        return self.exec_cmd_fn(cmd_fn, cmd_src, data, stdout_obj, stderr_obj)

    def exec_cmd_expr(
        self,
        cmd_expr: past.CmdExpr,
        stdin: str,
    ) -> int | str:
        # DEBUG: Expression execute time start
        _t_exec_expr = time.perf_counter_ns()

        syn_chk_res = self.syn_chk(cmd_expr)
        if syn_chk_res:
            return syn_chk_res

        err_code = uerr.ERR_ALL_GOOD
        skip = 0
        # Empty command, and cmd_expr will ALWAYS have one SimpCmd object in
        # simp_cmds list, even if the input line was empty
        if not cmd_expr.simp_cmds[0].params:
            return self.intrpr_vars["LAST_RET"]

        ugen.debug(
            ugen.fmt_d_stmt(
                "gen",
                "exec expr",
                cmd_expr
            )
        )

        for i, simp_cmd in enumerate(cmd_expr):
            if skip:
                skip -= 1
                continue

            op = cmd_expr.get_op(i)
            params = simp_cmd.params
            # Resolve command
            cmd_nm = params[0].val
            params = params[1 :]
            aliases = self.intrpr_vars["ALIASES"]
            cmd_resln_res = self.cmd_resln(cmd_nm)
            if cmd_nm in aliases:
                params_cp = list(params)
                for i, param in enumerate(params_cp):
                    if isinstance(param, past.Quoted):
                        params_cp[i] = quote + param.val + quote
                        continue
                    params_cp[i] = param.val
                # If a string is returned, it means command is an alias
                return aliases[cmd_nm] + " " + " ".join(params_cp)

            if isinstance(cmd_resln_res, int):
                return cmd_resln_res
            cmd_fn = cmd_resln_res.cmd_fn
            cmd_spec = cmd_resln_res.cmd_spec
            cmd_src = cmd_resln_res.cmd_src

            is_tty = True
            is_pipe = isinstance(op, past.Pipe)
            is_redir_stdout = isinstance(op, past.RedirSTDOUT)
            is_redir_stderr = isinstance(op, past.RedirSTDERR)
            old_stdout = stdout_obj = sys.stdout
            old_stderr = stderr_obj = sys.stderr

            # I don't know what the problem is, but I have to do those to make
            # piping work for expressions involving built-in commands
            if is_pipe or is_redir_stdout or is_redir_stderr:
                is_tty = False
            # Pipe
            if is_pipe:
                buf_stdout = io.StringIO()
                stdout_obj = buf_stdout
                if cmd_src == "built-in":
                    sys.stdout = buf_stdout
            # Redirect STDOUT
            elif is_redir_stdout:
                # get_simp_cmd can be called without worry because the syntax
                # is guaranteed to be ok, checked by syn_chk at the start of
                # this method. So, there shall be atleast one element in
                # parameter list of the SimpCmd objects
                redir_param = cmd_expr.get_simp_cmd(i + 1).get_param(0)
                redir_flnm = redir_param.val
                err_msg_head = "redirect STDOUT failed"
                try:
                    stdout_fl = open(redir_flnm, "w")
                except IsADirectoryError:
                    ugen.err_Q(
                        f"{err_msg_head}; is a directory: \"{redir_flnm}\" (pos {redir_param.start})"
                    )
                    return uerr.ERR_IS_A_DIR
                except PermissionError:
                    ugen.err_Q(
                        f"{err_msg_head}; access denied: \"{redir_flnm}\""
                    )
                    return uerr.ERR_PERM_DENIED
                except OSError as e:
                    # TODO: Change the error code later
                    ugen.err_Q(f"{err_msg_head}; OS error; {e.strerror}")
                    return uerr.ERR_OS_ERR
                stdout_obj = stdout_fl
                skip += 1
                if cmd_src == "built-in":
                    sys.stdout = stdout_fl
            # Redirect STDERR
            elif is_redir_stderr:
                redir_flnm = cmd_expr.get_simp_cmd(i + 1).get_param(0)
                err_msg_head = "redirect STDERR failed"
                try:
                    stderr_fl = open(redir_flnm.val, "w")
                except IsADirectoryError:
                    ugen.err_Q(f"{err_msg_head}; is a directory: \"{redir_flnm}\"")
                    return uerr.ERR_IS_A_DIR
                except PermissionError:
                    ugen.err_Q(
                        f"{err_msg_head}; access denied: \"{redir_flnm}\""
                    )
                    return uerr.ERR_PERM_DENIED
                except OSError as e:
                    ugen.err_Q(
                        f"{err_msg_head}; OS error; {e.strerror}"
                    )
                    return uerr.ERR_OS_ERR
                stderr_obj = stderr_fl
                skip += 1
                if cmd_src == "built-in":
                    sys.stderr = stderr_fl

            try:
                res = self.exec_cmd(
                    cmd_nm,
                    cmd_fn,
                    cmd_spec,
                    cmd_src,
                    params,
                    is_tty,
                    stdin,
                    stdout_obj,
                    stderr_obj
                )
                err_code = err_code or res.err_code
            finally:
                # Undo changes made for built-in commands
                if cmd_src == "built-in":
                    if is_pipe or is_redir_stdout:
                        sys.stdout = old_stdout
                    elif is_redir_stderr:
                        sys.stderr = old_stderr

            stdin = ""
            if is_pipe:
                stdin = buf_stdout.getvalue()
                ugen.debug(
                    ugen.fmt_d_stmt(
                        "gen",
                        f"STDIN from '{cmd_nm}'",
                        f"{len(stdin)} chrs"
                    )
                )

        # DEBUG: Expression execute time end
        ugen.debug_Q(
            ugen.fmt_d_stmt(
                "time",
                "expr_exec",
                self.fmt_t_ns(time.perf_counter_ns() - _t_exec_expr)
            )
        )
        return err_code

    def exec_cmd_seq(self, cmd_seq: past.CmdSeq):
        err_code = uerr.ERR_ALL_GOOD
        # DEBUG: Full sequence execute time start
        _t_full_seq = time.perf_counter_ns()

        idx = 0
        while idx < len(cmd_seq):
            cmd_expr = cmd_seq[idx]
            err_code_or_alias = self.exec_cmd_expr(cmd_expr, stdin="")
            # If that return value is a string, it means command was an alias,
            # and sequence needs to be edited
            if isinstance(err_code_or_alias, str):
                cmd_seq.pop(idx)
                cmd_seq[idx : idx] = self.parser.get_cmd_seq(
                    err_code_or_alias,
                    self.usr_dir,
                    os.getcwd(),
                    start=0
                )
                continue
            err_code = err_code_or_alias
            idx += 1

        # DEBUG: Full sequence execute time end
        ugen.debug_Q(
            ugen.fmt_d_stmt(
                "time",
                "full_seq_exec",
                self.fmt_t_ns(time.perf_counter_ns() - _t_full_seq)
            )
        )
        return err_code

    def syn_chk(self, cmd_expr: past.CmdExpr) -> int:
        num_ops = len(cmd_expr.ops)
        i = 0

        while i < num_ops:
            l_simp_cmd = cmd_expr.get_simp_cmd(i)
            r_simp_cmd = cmd_expr.get_simp_cmd(i + 1)
            op = cmd_expr.get_op(i)

            # No parameters on the right of operator
            if r_simp_cmd is None:
                ugen.err_Q(
                    f"Expected at least one parameter on the right of operator at pos {op.end}"
                )
                return uerr.ERR_EXPD_PARAM_RT_OP
            if len(r_simp_cmd) < 1:
                ugen.err_Q(
                    f"Missing parameter for operator '{op}' at pos {op.end}"
                )
                return uerr.ERR_EXPD_PARAM_RT_OP
            # Too many parameters on the right of STDOUT redirect operator
            if isinstance(op, past.RedirSTDOUT) and len(r_simp_cmd) > 1:
                ugen.err_Q(
                    f"Unexpected parameter for STDOUT redirection at pos {r_simp_cmd.params[1].start}"
                )
                return uerr.ERR_UNEXPD_PARAM_STDOUT_REDIRN
            # Too many parameters on the right of STDERR redirect operator
            elif isinstance(op, past.RedirSTDERR) and len(r_simp_cmd) > 1:
                ugen.err_Q(
                    f"Unexpected parameter for STDERR redirection at pos {r_simp_cmd.params[1].start}"
                )
                return uerr.ERR_UNEXPD_PARAM_STDOUT_REDIRN

            i += 1

        return uerr.ERR_ALL_GOOD

    def rn_cmd_fn(self, cmd_fn: TH_CmdFn, data: ugen.CmdData) -> int:
        """
        Run a command function.

        :param cmd_fn: Command function to execute.
        :type cmd_fn: TH_CmdFn

        :param data: Data to be passed to the command function.
        :type data: utils.gen.CmdData

        :returns: Integer error code.
        :rtype: int
        """
        cmd_ret = uerr.ERR_ALL_GOOD

        # DEBUG: Run command function time start
        _t_rn_cmd_fn = time.perf_counter_ns()

        try:
            cmd_ret = cmd_fn(data)
        # Variable type mismatch
        except ugen.InvVarTypErr as e:
            cmd_ret = cmd_ret or uerr.ERR_ENV_VAR_INV_TYP
            ugen.err_Q(
                f"Invalid variable type for '{e.var_nm}'; expected '{e.var_typ.__name__}', got '{e.got_typ.__name__}'"
            )
        # Invalid variable name
        except ugen.InvVarNmErr as e:
            cmd_ret = cmd_ret or uerr.ERR_ENV_VAR_INV_NM
            ugen.err_Q(f"Invalid variable name: '{e.var_nm}'")
        # Unknown variable
        except ugen.UnkVarErr as e:
            cmd_ret = cmd_ret or uerr.ERR_ENV_UNK_VAR
            ugen.err_Q(f"Unknown variable: '{e.var_nm}'")

        # DEBUG: Run command function time end
        ugen.debug(
            ugen.fmt_d_stmt(
                "time",
                "rn_cmd_fn",
                self.fmt_t_ns(time.perf_counter_ns() - _t_rn_cmd_fn)
            )
        )
        return cmd_ret

    def exec(self, ln: str):
        tmp = self.parser.get_cmd_seq(ln, self.usr_dir, os.getcwd(), start=0)
        if isinstance(tmp, int):
            return tmp
        return self.exec_cmd_seq(tmp)
