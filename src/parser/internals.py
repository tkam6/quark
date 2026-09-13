import dataclasses as dcs


@dcs.dataclass
class Tok:
    val: str
    quoted: bool
    quote_typ: str | None
    start: int
    end: int
    escd_hyphen: bool = False

    def __repr__(self) -> str:
        return f"TOK[val={self.val} quoted={self.quoted} start={self.start} end={self.end}]"

    def __str__(self) -> str:
        return self.__repr__()


@dcs.dataclass
class SpChr:
    val: str
    start: int
    end: int

    def __repr__(self) -> str:
        return f"SP_CHR[val={self.val} start={self.start} end={self.end}]"

    def __str__(self) -> str:
        return self.__repr__()


QUOTES = ("'", "\"", "`")
LOGI_OPS = ("&", "^")
DATA_OPS = ("|", ">", "?")
CMD_SEPRS = (";",)
GLOB_CHS = ("*",)
DIR_EXP_CHRS = {"\\~": "~"}
ESC_CHR_MAP = {
    "\\\\": "\\",
    "\\'": "'",
    "\\\"": "\"",
    "\\n": "\n",
    "\\t": "\t",
}
# No duplicate values in the values of this dictionary
assert len(set(ESC_CHR_MAP.values())) == len(ESC_CHR_MAP.values())
REV_ESC_CHR_MAP = {v: k for (k, v) in ESC_CHR_MAP.items()}
