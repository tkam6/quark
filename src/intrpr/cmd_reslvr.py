import hashlib as hl
import importlib as il
import importlib.util as ilu
import os
import pathlib as pl
import pkgutil as pu
import time
import traceback as tb
import types
import typing as ty

from src.intrpr import internals as iint
from src.utils import consts as uconst
from src.utils import err_codes as uerr
from src.utils import gen as ugen


class CmdReslvr:
    def __init__(
            self,
            ext_cached_cmds: dict[str, iint.CmdCacheEntry],
            debug_time_expo: int
        ) -> None:

        self.builtin_cmds: dict[
            str,                                   # Command name
            tuple[
                ty.Callable[[ugen.CmdData], int],  # Command function
                ugen.CmdSpec,                      # Command spec
                ugen.HelpObj                       # Help string
            ]
        ]

        self.debug_time_expo = debug_time_expo
        self.builtin_cmds = {}
        self.gather_builtin_cmds()

    def fmt_t_ns(self, ns: int) -> str:
        return ugen.fmt_t_ns(self.debug_time_expo, ns)

    def _compu_fl_hash(
        self,
        fl_pth: str,
        buf_sz: int = 65536     # 64KiB chunks
    ) -> str | int:
        ugen.info(f"file provided: {fl_pth}")
        # DEBUG: Hash time start
        _t_hash = time.perf_counter_ns()

        sha256 = hl.sha256()
        try:
            with open(fl_pth, "rb") as f:
                while data := f.read(buf_sz):
                    sha256.update(data)
        except FileNotFoundError:
            return uerr.ERR_FL_404
        except PermissionError:
            return uerr.ERR_PERM_DENIED
        except IsADirectoryError:
            return uerr.ERR_IS_A_DIR
        except OSError:
            return uerr.ERR_OS_ERR
        except Exception:
            return uerr.ERR_UNK_ERR
        fl_hash = sha256.hexdigest()
        # DEBUG: Hash time end
        _t_hash = time.perf_counter_ns() - _t_hash
        ugen.debug_Q(
            ugen.fmt_d_stmt(
                "time",
                f"fl_hash {os.path.splitext(os.path.basename(fl_pth))[0]}",
                self.fmt_t_ns(_t_hash)
            )
        )
        ugen.info(f"file hash: {fl_hash}")
        return fl_hash

    def _is_new_ld_reqd(
        self,
        fl_stat: os.stat_result,
        fl_pth: str,
        cache_entry: iint.CmdCacheEntry
    ) -> bool:
        return (
            fl_stat.st_mtime != cache_entry.mtime
            or fl_stat.st_size != cache_entry.sz
            or fl_pth != cache_entry.pth
            or self._compu_fl_hash(fl_pth) != cache_entry.fl_hash
        )

    def ld_mod(
        self,
        cmd: str,
        ext_cached_cmds: dict[str, iint.CmdCacheEntry],
        dir_pths: tuple[str],
    ) -> types.ModuleType | int:
        fl: pl.Path

        if "/" in cmd or "\0" in cmd:
            return uerr.ERR_BAD_CMD

        # DEBUG: Module load time start
        _t_mod_ld = time.perf_counter_ns()

        for dir_pth in dir_pths:
            fl_str = os.path.join(dir_pth, cmd + ".py")
            fl = pl.Path(fl_str).expanduser().resolve().absolute()
            fl_stat = None
            cache_entry = ext_cached_cmds.get(cmd)
            try:
                fl_stat = fl.stat(follow_symlinks=False)
            except FileNotFoundError:
                continue
            # This fucking thing is raised when something like `./ls/` is input
            except NotADirectoryError:
                continue

            if (
                cache_entry is not None
                and not self._is_new_ld_reqd(fl_stat, str(fl), cache_entry)
            ):
                return cache_entry.mod

            mod_spec = ilu.spec_from_file_location(cmd, fl)
            if mod_spec is None or mod_spec.loader is None:
                continue

            # Try to load the module from the spec
            try:
                cmd_mod = ilu.module_from_spec(mod_spec)
                mod_spec.loader.exec_module(cmd_mod)
            # ImportError is raised if the spec has a exec_module() attribute but
            # not a create_module() attribute, which I understand nothing about
            # right now.
            # FileNotFoundError is raised by _io.open_code(...) in
            # importlib._bootstrap_external.py if the file is not found [called due
            # to loader.exec_module(...)]
            except (FileNotFoundError, ImportError):
                continue
            except SyntaxError:
                ugen.crit_Q(
                    f"Syntax error in command module '{cmd}'",
                    exc_txt=(f"(resolver) Syntax error in command module '{cmd}':\n"
                             f"{tb.format_exc()}")
                )
                return uerr.ERR_CMD_SYN_ERR
            except Exception as e:
                ugen.crit_Q(
                    f"Loading '{cmd}' raised {e.__class__.__name__}",
                    exc_txt=(f"(resolver) Loading '{cmd}' raised:\n"
                             f"{tb.format_exc()}")
                )
                return uerr.ERR_CANT_LD_CMD_MOD
            # except RecursionError:
            #     return uerr.ERR_RECUR_ERR

            validate_res = self.validate_cmd_mod(cmd_mod)
            if validate_res != uerr.ERR_ALL_GOOD:
                return validate_res

            ext_cached_cmds[cmd] = iint.CmdCacheEntry(
                cmd,
                mod_spec,
                cmd_mod,
                str(fl),
                self._compu_fl_hash(str(fl)),
                fl_stat.st_size,
                fl_stat.st_mtime
            )

            # DEBUG: Module load time end
            _t_mod_ld = time.perf_counter_ns() - _t_mod_ld
            ugen.debug_Q(
                ugen.fmt_d_stmt(
                    "time",
                    f"ld_mod {cmd}",
                    self.fmt_t_ns(_t_mod_ld)
                )
            )

            return cmd_mod

        return uerr.ERR_BAD_CMD

    def validate_cmd_mod(self, cmd_mod: types.ModuleType) -> int:
        has_cmd_fn = hasattr(cmd_mod, "run")
        has_cmd_spec = hasattr(cmd_mod, "CMD_SPEC")
        has_help_obj = hasattr(cmd_mod, "HELP")
        if not has_cmd_fn:
            return uerr.ERR_NO_CMD_FN
        if not has_cmd_spec:
            return uerr.ERR_NO_CMD_SPEC
        if not has_help_obj:
            return uerr.ERR_NO_HELP_OBJ

        # Get help object, command spec and function and validate
        cmd_fn = cmd_mod.run
        cmd_spec = cmd_mod.CMD_SPEC
        help_obj = cmd_mod.HELP
        is_fn_callable = callable(cmd_fn)
        is_num_fn_params_ok = (is_fn_callable
                               and cmd_fn.__code__.co_argcount == 1)
        is_spec_ok = isinstance(cmd_spec, ugen.CmdSpec)
        is_help_ok = isinstance(help_obj, ugen.HelpObj)
        if not is_fn_callable:
            return uerr.ERR_UNCALLABLE_CMD_FN
        if not is_num_fn_params_ok:
            return uerr.ERR_INV_NUM_PARAMS
        if not is_spec_ok:
            return uerr.ERR_INV_CMD_SPEC
        if not is_help_ok:
            return uerr.ERR_INV_HELP_OBJ

        return uerr.ERR_ALL_GOOD

    def gather_builtin_cmds(self) -> None:
        # DEBUG: Load built-in commands time start
        _t_ld_bcmds = time.perf_counter_ns()

        num_lded_builtin = 0
        builtins_lded = []

        for mod_fl in pu.iter_modules([uconst.BUILTIN_PTH]):
            if mod_fl.name == "__init__":
                continue

            cmd_nm = mod_fl.name
            mod = il.import_module(f"intrpr.builtin_cmds.{cmd_nm}")
            help_obj = mod.HELP
            cmd_spec = mod.CMD_SPEC
            cmd_fn = mod.run

            self.builtin_cmds[cmd_nm] = (cmd_fn, cmd_spec, help_obj)
            builtins_lded.append(cmd_nm)
            num_lded_builtin += 1

        # DEBUG: Load built-in commands time end
        _t_ld_bcmds = time.perf_counter_ns() - _t_ld_bcmds

        ugen.debug_Q(ugen.fmt_d_stmt("ld_bltns", ", ".join(builtins_lded)))
        ugen.debug_Q(
            ugen.fmt_d_stmt("time", "tot_ld_bltns", self.fmt_t_ns(_t_ld_bcmds))
        )
        ugen.info_Q(f"built-ins loaded: {num_lded_builtin}")

    def get_builtin_help(self, cmd: str) -> ugen.HelpObj | int:
        tmp = self.builtin_cmds.get(cmd)
        if tmp is None:
            return uerr.ERR_BAD_CMD
        help_obj = tmp[2]
        return help_obj

    def get_ext_help(
        self,
        cmd: str,
        ext_cached_cmds: dict[str, iint.CmdCacheEntry],
        pths: tuple[str, ...]
    ) -> ugen.HelpObj | int:
        tmp_mod = self.ld_mod(cmd, ext_cached_cmds, pths)
        if isinstance(tmp_mod, int):
            return tmp_mod
        cmd_mod = tmp_mod
        # validate_res = self.validate_cmd_mod(cmd_mod)
        # if validate_res != uerr.ERR_ALL_GOOD:
        #     return validate_res
        help_obj = cmd_mod.HELP
        return help_obj

    def get_builtin_cmd(self, cmd: str) -> \
            tuple[ty.Callable[[ugen.CmdData], int], ugen.CmdSpec] | int:
        # Built-in help objects, command specs and functions are assumed valid
        tmp = self.builtin_cmds.get(cmd)
        if tmp is None:
            return uerr.ERR_BAD_CMD
        cmd_fn, cmd_spec, _ = tmp
        return cmd_fn, cmd_spec

    def get_ext_cmd(
        self,
        cmd: str,
        pths: tuple[str],
        ext_cached_cmds: dict[str, iint.CmdCacheEntry]
    ) -> tuple[ty.Callable[[ugen.CmdData], int], ugen.CmdSpec] | int:
        tmp_mod = self.ld_mod(cmd, ext_cached_cmds, pths)
        if isinstance(tmp_mod, int):
            return tmp_mod
        cmd_mod = tmp_mod
        # validate_res = self.validate_cmd_mod(cmd_mod)
        # if validate_res != uerr.ERR_ALL_GOOD:
        #     return validate_res
        cmd_spec = cmd_mod.CMD_SPEC
        cmd_fn = cmd_mod.run
        return (cmd_fn, cmd_spec)
