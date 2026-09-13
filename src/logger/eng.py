import enum
import io
import os
import typing as ty

from src.utils import gen as ugen


class LogLvls(enum.IntEnum):
    DEBUG = 1
    INFO = enum.auto()
    WARN = enum.auto()
    ERR = enum.auto()
    CRIT = enum.auto()
    FATAL = enum.auto()


class LogData(ty.NamedTuple):
    nm: str
    msg: str
    lvl: int


class Lgr:
    def __init__(
        self,
        nm: str,
        src: str,
        lvl: int,
        stream: io.TextIOBase
    ) -> None:
        self.nm = nm
        self.src = src
        self.lvl = lvl
        self.stream = stream
        self.fl_num = self.stream.fileno()

    def _log(self, msg: str, lvl: int, fmting: str | None = None) -> None:
        if lvl < self.lvl:
            return
        os.write(
            self.fl_num,
            (
                (fmting if fmting is not None else "")
                + ERR_HEADER_MAP[lvl]
                + self.src
                + (ugen.S.reset if fmting is not None else "")
                + f" {msg}\n"
            ).encode()
        )

    def debug(self, msg: str) -> None:
        self._log(msg, LogLvls.DEBUG, fmting=ugen.S.bold)

    def info(self, msg: str) -> None:
        self._log(msg, LogLvls.INFO, fmting=ugen.S.bold)

    def warn(self, msg: str) -> None:
        self._log(msg, LogLvls.WARN, fmting=ugen.S.bold + ugen.S.yellow_4)

    def err(self, msg: str) -> None:
        self._log(msg, LogLvls.ERR, fmting=ugen.S.bold + ugen.S.red_4)

    def crit(self, msg: str) -> None:
        self._log(msg, LogLvls.CRIT, fmting=ugen.S.bold + ugen.S.red_4)

    def fatal(self, msg: str) -> None:
        self._log(msg, LogLvls.FATAL, fmting=ugen.S.bold + ugen.S.red_4)


class LgrVessel(ty.NamedTuple):
    lgr_c: Lgr
    lgr_q: Lgr
    fl_lgr: Lgr


ERR_HEADER_MAP: dict[int, str]
ERR_HEADER_MAP = {
    LogLvls.DEBUG: "D",
    LogLvls.INFO : "I",
    LogLvls.WARN : "W",
    LogLvls.ERR  : "E",
    LogLvls.CRIT : "C",
    LogLvls.FATAL: "F"
}
