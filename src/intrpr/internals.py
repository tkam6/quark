# TODO: tmp; remove
import pdb

import collections.abc as cabc
import copy
import ctypes as ct
import dataclasses as dcs
import functools
import importlib.machinery as ilm
import struct as st
import threading as th
import traceback as tb
import typing as ty
import types
if ty.TYPE_CHECKING:
    import multiprocessing.shared_memory as mpshm
    import multiprocessing.synchronize as mpsync

from src.utils import err_codes as uerr
from src.utils import gen as ugen
if ty.TYPE_CHECKING:
    from src.intrpr import cmd_reslvr as icrsr


# To not lose the traceback string (yes, string) during the pickling process;
# stores the traceback as a string in an attribute, as the __traceback__
# attribute of the exceptions gets dropped during pickling
class ExcepWNoLoss:
    def __init__(self, e: Exception) -> None:
        self.e = e
        self.exc_txt = tb.format_tb(self.e.__traceback__)


class CmdCompdObj(ty.NamedTuple):
    err_code: int


class CmdCacheEntry(ty.NamedTuple):
    cmd: str
    spec: ilm.ModuleSpec
    mod: types.ModuleType
    pth: str
    fl_hash: int
    sz: int
    mtime: float


class CmdReslnRes(ty.NamedTuple):
    cmd_fn: ty.Callable[[ugen.CmdData], int]
    cmd_spec: ugen.CmdSpec
    cmd_src: str


class Snoo:
    def __init__(self) -> None:
        self.CMD_SPEC = ugen.CmdSpec(
            min_args=0,
            max_args=float("inf"),
            opts=(),
            flags=("-C", "--no-crash"),
            parse_sub_cmds=False
        )
        self.HELP = ugen.HelpObj(
            usage="snoo [flag] [...]",
            summary="Oh, you'll see...",
            details=(
                "ARGUMENTS",
                ("none", ""),
                "OPTIONS",
                ("none", ""),
                "FLAGS",
                ("-C, --no-crash", "Do not crash the interpreter")
            )
        )

    def run(self, data: ugen.CmdData) -> int | ty.NoReturn:
        crash = True
        for flag in data.flags:
            if flag in ("-C", "--no-crash"):
                crash = False
        if crash:
            ugen.fatal_Q("Beauty overload", ret=uerr.ERR_MP_BEAUTY_OVERLD)
        else:
            ugen.crit_Q("Beauty overload")
            return uerr.ERR_BEAUTY_OVERLD


def catch_exceps_env_tbl(
        f: ty.Callable[..., ty.Any]
        ) -> ty.Callable[..., ty.Any] | ty.NoReturn:
    @functools.wraps(f)
    def fn(*args, **kwargs) -> ty.Any | ty.NoReturn:
        try:
            return f(*args, **kwargs)
        except st.error:
            ugen.fatal_Q(
                "Corrupted shared memory; cannot continue execution",
                ret=uerr.ERR_CORRUPTED_ENV_TBL
            )
        except ugen.EnvKeyTooLarge as e:
            key = e.offending_key
            key = (key[: 10] + "...") if len(key) > 10 else key
            ugen.err_Q(f"Env var key too large: {key}")
        except ugen.EnvValTooLarge as e:
            val = e.offending_val
            val = (val[: 10] + "...") if len(val) > 10 else val
            ugen.err_Q(f"Env var value too large: {val}")
    return fn


@dcs.dataclass
class EnvTbl:
    """
    Structure in memory:
    .+++++++++++++++,
    |     count     |  --> 8B
    `---------------'
    .+++++++++++++++,
    |  key lengths  |  --> 8B * number of entires
    |      ...      |
    `---------------'
    .+++++++++++++++,
    | value lengths |  --> 8B * number of entries
    |      ...      |
    `---------------'
    .+++++++++++++++,
    |     keys      |  --> 128B * number of entries
    |      ...      |
    `---------------'
    .+++++++++++++++,
    |     values    |  --> 8048B * number of entries
    |      ...      |
    `---------------'
    Idea is that there shall be 8192B per entry.
    """
    _shm: "mpshm.SharedMemory"
    lock: "mpsync.RLock"

    def __post_init__(self) -> None:
        self.SHM_SZ = self.shm.size
        self.CNT_SZ = 8                 # Size to store number of items
        self.KEY_LEN_SZ = 8             # Size to store key length
        self.VAL_LEN_SZ = 8             # Size to store value length
        self.KEY_ENTRY_SZ = 128         # Entry size of key
        self.VAL_ENTRY_SZ = 8048        # Entry size of value
        self.ENTRY_BYTES_REQD = (       # Memory required for each entry
            self.KEY_LEN_SZ
            + self.VAL_LEN_SZ
            + self.KEY_ENTRY_SZ
            + self.VAL_ENTRY_SZ
        )
        self.MAX_ITEMS = (self.SHM_SZ - 8) // self.ENTRY_BYTES_REQD
        self.CNT_START = 0                                                                  # Start offset of number of items
        self.ARR_KEY_LEN_START = self.CNT_START + self.CNT_SZ                               # Start offset of array of key lengths
        self.ARR_VAL_LEN_START = self.ARR_KEY_LEN_START + self.MAX_ITEMS * self.KEY_LEN_SZ  # Start offset of array of value lengths
        self.ARR_KEYS_START = self.ARR_VAL_LEN_START + self.MAX_ITEMS * self.VAL_LEN_SZ     # Start offset of array of keys
        self.ARR_VALS_START = self.ARR_KEYS_START + self.MAX_ITEMS * self.KEY_ENTRY_SZ      # Start offset of array of values
        self._wrt_u64(0, self.CNT_START, self.CNT_START + self.CNT_SZ)

        self.occupied = [False for _ in range(self.MAX_ITEMS)]

    def __bool__(self) -> bool:
        return bool(len(self))

    def __len__(self) -> int:
        return self._rd_u64(self.CNT_START, self.CNT_START + self.CNT_SZ)

    def __iter__(self) -> ty.Iterable[tuple[str, str]]:
        for i in range(self.MAX_ITEMS):
            if not self._chk_key_occupancy(i):
                continue
            yield self.get_by_idx(i)

    def __contains__(self, key: ty.Any) -> bool:
        try:
            self.get(key)
            return True
        except ugen.UnkVarErr:
            return False

    def __getitem__(self, key: str) -> ty.Any | ty.NoReturn:
        return self.get(key)

    def __setitem__(self, key: str, val: str) -> None | ty.NoReturn:
        return self.set(key, val)

    def __repr__(self) -> str:
        data_dict = {}
        for pair in self:
            data_dict[pair[0]] = pair[1]
        return str(data_dict)

    @property
    def shm(self) -> "mpshm.SharedMemory":
        if self._shm is None:
            raise ugen.EnvTblShmNone("Operation on closed shared memory descriptor")
        return self._shm

    @shm.setter
    def shm(self, val: ty.Any) -> None:
        self._shm = val

    @property
    def buf(self) -> memoryview:
        if self.shm.buf is None:
            raise ugen.EnvTblShmBufNone()
        return self.shm.buf

    def _chk_key_occupancy(self, idx: int) -> bool:
        start = self.ARR_KEY_LEN_START + self.KEY_LEN_SZ * idx
        return self._rd_u64(start, start + self.KEY_LEN_SZ) != 0

    @catch_exceps_env_tbl
    def _rd_u64(self, start: int, end: int) -> int:
        return st.unpack("!Q", self.buf[start : end])[0]

    @catch_exceps_env_tbl
    def _rd_str(self, start: int, end: int) -> str:
        return self.buf[start : end].tobytes().decode()

    @catch_exceps_env_tbl
    def _wrt_u64(self, data: int, start: int, end: int) -> None:
        # TODO: Add checks for size (u64 is 8 bytes, etc.)
        with self.lock:
            self.buf[start : end] = st.pack("!Q", data)

    @catch_exceps_env_tbl
    def _wrt_str(self, data: str, start: int, end: int) -> None:
        with self.lock:
            self.buf[start : end] = data.encode()

    @catch_exceps_env_tbl
    def set(self, key: str, val: str) -> None | ty.NoReturn:
        # Validate key and val are strings
        if not isinstance(key, str):
            raise ugen.InvVarNmErr(var_nm=key)
        if not isinstance(val, str):
            raise ugen.InvVarValErr(var_nm=key, var_val=val)
        # Validate identifier name
        if (
            key.lower().strip("_abcdefghijklmnopqrstuvwxyz0123456789")
            or key.startswith("0123456789")
        ):
            raise ugen.InvVarNmErr(var_nm=key)

        # Validate data received (key and value)
        encoded_key = key.encode()
        encoded_val = val.encode()
        len_encoded_key = len(key.encode())
        len_encoded_val = len(val.encode())
        # Check if length of key and value are more than allowed
        if len_encoded_key > self.KEY_ENTRY_SZ:
            raise ugen.EnvKeyTooLarge("", offending_key=key)
        if len_encoded_val > self.VAL_ENTRY_SZ:
            raise ugen.EnvValTooLarge("", offending_val=val)

        with self.lock:
            # If key already exists, just update it
            for i in range(self.MAX_ITEMS):
                # Skip if empty cell
                if not self._chk_key_occupancy(i):
                    continue

                cur_key, cur_val = self.get_by_idx(i)
                if cur_key != key:
                    continue
                arr_val_len_entry_idx = self.ARR_VAL_LEN_START + self.VAL_LEN_SZ * i
                arr_val_entry_idx = self.ARR_VALS_START + self.VAL_ENTRY_SZ * i
                self._wrt_u64(len_encoded_val, arr_val_len_entry_idx, arr_val_len_entry_idx + self.VAL_LEN_SZ)
                self._wrt_str(val, arr_val_entry_idx, arr_val_entry_idx + len_encoded_val)
                return

            # If the key doesn't already exist, then create a new one
            for i in range(self.MAX_ITEMS):
                # If key already exists, skip
                if self._chk_key_occupancy(i):
                    continue

                arr_key_len_entry_idx = self.ARR_KEY_LEN_START + self.KEY_LEN_SZ * i
                arr_val_len_entry_idx = self.ARR_VAL_LEN_START + self.VAL_LEN_SZ * i
                arr_key_entry_idx = self.ARR_KEYS_START + self.KEY_ENTRY_SZ * i
                arr_val_entry_idx = self.ARR_VALS_START + self.VAL_ENTRY_SZ * i
                self._wrt_u64(len_encoded_key, arr_key_len_entry_idx, arr_key_len_entry_idx + self.KEY_LEN_SZ)
                self._wrt_u64(len_encoded_val, arr_val_len_entry_idx, arr_val_len_entry_idx + self.VAL_LEN_SZ)
                self._wrt_str(key, arr_key_entry_idx, arr_key_entry_idx + len_encoded_key)
                self._wrt_str(val, arr_val_entry_idx, arr_val_entry_idx + len_encoded_val)
                self._wrt_u64(len(self) + 1, self.CNT_START, self.CNT_START + self.CNT_SZ)
                return

        raise ugen.HowDidWeGetHere()

    def get(self, key: str) -> str | ty.NoReturn:
        cur_val = None
        for i in range(self.MAX_ITEMS):
            arr_key_len_entry_idx = self.ARR_KEY_LEN_START + self.KEY_LEN_SZ * i
            key_len = self._rd_u64(arr_key_len_entry_idx, arr_key_len_entry_idx + self.KEY_LEN_SZ)
            if key_len == 0:
                continue
            cur_key, cur_val = self.get_by_idx(i)
            if key == cur_key:
                return cur_val
        raise ugen.UnkVarErr(var_nm=key)

    def get_by_idx(self, idx: int) -> tuple[str, str] | ty.NoReturn:
        if idx > self.MAX_ITEMS - 1:
            raise IndexError()

        key_len_start = self.ARR_KEY_LEN_START + idx * self.KEY_LEN_SZ
        key_start = self.ARR_KEYS_START + idx * self.KEY_ENTRY_SZ
        key_len = self._rd_u64(key_len_start, key_len_start + self.KEY_LEN_SZ)
        cur_key = self._rd_str(key_start, key_start + key_len)

        val_len_start = self.ARR_VAL_LEN_START + idx * self.VAL_LEN_SZ
        val_start = self.ARR_VALS_START + idx * self.VAL_ENTRY_SZ
        val_len = self._rd_u64(val_len_start, val_len_start + self.VAL_LEN_SZ)
        cur_val = self._rd_str(val_start, val_start + val_len)
        return (cur_key, cur_val)

    def rm(self, nm: str) -> None:
        with self.lock:
            for i in range(self.MAX_ITEMS):
                if not self._chk_key_occupancy(i):
                    continue
                key_len_start = self.ARR_KEY_LEN_START + i * self.KEY_LEN_SZ
                key_start = self.ARR_KEYS_START + i * self.KEY_ENTRY_SZ
                key_len = self._rd_u64(key_len_start, key_len_start + self.KEY_LEN_SZ)
                cur_key = self._rd_str(key_start, key_start + key_len)
                if cur_key != nm:
                    continue
                self._wrt_u64(0, key_len_start, key_len_start + self.KEY_LEN_SZ)
                self._wrt_u64(len(self) - 1, self.CNT_START, self.CNT_START + self.CNT_SZ)
                # TODO: erase key, value and value length if needed
                return

        raise ugen.InvVarNmErr(var_nm=nm)


@dcs.dataclass
class IntrprTbl:
    intrpr_tbl: dict[str, ty.Any] = dcs.field(default_factory=dict)
    protection_status: dict[str, bool] = dcs.field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.intrpr_tbl)

    def __iter__(self) -> ty.NoReturn:
        yield from self.intrpr_tbl

    def __contains__(self, key: ty.Any) -> bool:
        return key in self.intrpr_tbl

    def __getitem__(self, key: str) -> ty.Any | ty.NoReturn:
        if key not in self.intrpr_tbl:
            raise ugen.UnkVarErr(var_nm=key)
        return self.get(key)

    def __setitem__(self, key: str, val: ty.Any) -> None | ty.NoReturn:
        if key not in self.intrpr_tbl:
            if (
                key.lower().strip("_abcdefghijklmnopqrstuvwxyz0123456789")
                or key.startswith("0123456789")
            ):
                raise ugen.InvVarNmErr(var_nm=key)
        self.set(key, val)

    def __repr__(self) -> str:
        return str(self.intrpr_tbl)

    def set(
        self,
        nm: str,
        val: ty.Any,
        protected: bool = False
    ) -> None | ty.NoReturn:
        self.protection_status[nm] = protected
        self.intrpr_tbl[nm] = val

    def get(self, nm: str) -> ty.Any | ty.NoReturn:
        return self.intrpr_tbl[nm]

    def pop(self, nm: str) -> ty.Any | ty.NoReturn:
        try:
            # If protected, raise InvAccess
            if self.protection_status[nm]:
                raise ugen.InvAccess(f"Pop of protected variable: {nm}")
            return self.intrpr_tbl.pop(nm)
        except KeyError:
            pass

    def items(self) -> cabc.ItemsView[str, ty.Any]:
        return self.intrpr_tbl.items()

    def crt_self_cp(self) -> ty.Self:
        return copy.deepcopy(self)
