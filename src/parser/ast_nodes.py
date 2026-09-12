import dataclasses as dc
import typing as ty


@dc.dataclass(repr=False)
class Tok:
    val: str
    start: int
    end: int

    def __repr__(self) -> str:
        return repr(self.val)

    def __str__(self) -> str:
        return self.__repr__()

    def __len__(self) -> int:
        return len(self.val)


@dc.dataclass(repr=False)
class Op(Tok):
    pass


@dc.dataclass(repr=False)
class Param(Tok):
    escd_hyp: bool


@dc.dataclass(repr=False)
class DataOp(Op):
    def __repr__(self) -> str:
        return self.val


@dc.dataclass(repr=False)
class Pipe(DataOp):
    pass


@dc.dataclass(repr=False)
class RedirSTDOUT(DataOp):
    pass


@dc.dataclass(repr=False)
class RedirSTDERR(DataOp):
    pass


@dc.dataclass(repr=False)
class LogOp(Op):
    pass


@dc.dataclass(repr=False)
class And(LogOp):
    pass


@dc.dataclass(repr=False)
class Or(LogOp):
    pass


@dc.dataclass(repr=False)
class Unquoted(Param):
    pass


@dc.dataclass(repr=False)
class Quoted(Param):
    quote: str


@dc.dataclass(repr=False)
class SimpCmd:
    params: list[Param]

    def get_param(self, idx: int) -> Param | None:
        if idx >= len(self.params):
            return None
        return self.params[idx]

    def __bool__(self) -> bool:
        return bool(self.params)

    def __len__(self) -> int:
        return len(self.params)

    def __repr__(self) -> str:
        return f"S{self.params}"


@dc.dataclass(repr=False)
class CmdExpr:
    simp_cmds: list[SimpCmd]
    ops: list[Op]

    def get_op(self, idx: int) -> Op | None:
        if idx >= len(self.ops):
            return None
        return self.ops[idx]

    def get_simp_cmd(self, idx: int) -> SimpCmd | None:
        if idx >= len(self.simp_cmds):
            return None
        return self.simp_cmds[idx]

    def __repr__(self) -> str:
        # return f"E{self.simp_cmds};{self.ops}"
        return f"E{self.simp_cmds}"

    def __iter__(self) -> ty.Generator[SimpCmd, None, None]:
        for i in self.simp_cmds:
            yield i

    def __len__(self) -> int:
        return len(self.simp_cmds)


@dc.dataclass(repr=False)
class CmdSeq:
    cmds: list[CmdExpr]

    def __repr__(self) -> str:
        return f"SEQ{self.cmds}"

    def __iter__(self) -> ty.Generator[CmdExpr, None, None]:
        for i in self.cmds:
            yield i

    def __len__(self) -> int:
        return len(self.cmds)

    def __getitem__(self, idx_or_sl: int | slice) -> CmdExpr | list[CmdExpr]:
        return self.cmds[idx_or_sl]

    def __setitem__(
        self,
        idx_or_sl: int | slice,
        item: CmdExpr | list[CmdExpr]
    ) -> None:
        self.cmds[idx_or_sl] = item

    def pop(self, idx: int = -1) -> CmdExpr:
        return self.cmds.pop(idx)

    def insert(self, idx: int, item: CmdExpr) -> None:
        self.cmds.insert(idx, item)
