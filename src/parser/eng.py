from src.parser import ast_nodes as past
from src.parser import internals as pint
from src.utils import err_codes as uerr
from src.utils import gen as ugen


class Parser:
    def __init__(self) -> None:
        self.LOGI_OP_CHR_NODE_MAP = {
            "&": past.And,
            "^": past.Or
        }
        self.DATA_OP_CHR_NODE_MAP = {
            "|": past.Pipe,
            ">": past.RedirSTDOUT,
            "?": past.RedirSTDERR
        }

    def _get_unquoted_tok(self, ln: str, start: int) -> past.Param:
        """
        Get an unquoted token from the source line.

        :param ln: The source line to lex.
        :type ln: str

        :param start: The index to start lexing from in the source.
        :type start: int

        :returns: A token object.
        :rtype: parser.internals.Tok
        """
        idx = start

        for ch in ln[start :]:
            if ch.isspace():
                break
            if ch in pint.QUOTES and ln[idx - 1] != "\\":
                break
            if ch in (*pint.LOGI_OPS, *pint.DATA_OPS, *pint.CMD_SEPRS) and ln[idx - 1] != "\\":
                break
            idx += 1

        return past.Unquoted(
            val=ln[start : idx],
            escd_hyp=False,       # False for now, this will be updated
            start=start,
            end=idx
        )

    def _get_quoted_tok(
        self,
        ln: str,
        start: int,
        quote: str,
    ) -> past.Quoted | int:
        """
        Get a quoted token from the source line.

        :param ln: The source line to lex.
        :type ln: str
        :param start: The index to start lexing from in the source.
        :type start: int

        :param quote: The "quote" character to match to end the quoted token.
        :type quote: str

        :returns: A token object or error code.
        :rtype: parser.internals.Tok | int
        """
        # Exclude the opening quote from the index
        elem_start = idx = start + 1
        prev_chr = None

        for char in ln[elem_start :]:
            # Before the if statement to include the closing quote in the index
            idx += 1
            if char == quote and prev_chr != "\\":
                break
            prev_chr = char
        else:
            ugen.err_Q(f"No closing quote at position {idx}")
            return uerr.ERR_NO_CLOSING_QUOTE

        return past.Quoted(
            # Do not include the closin quote in the value
            ln[elem_start : idx - 1],
            escd_hyp=False,
            quote=quote,
            start=start,
            end=idx
        )

    def _get_nxt_param(
        self,
        ln: str,
        usr_dir: str,
        pth: str,
        do_shell_exp: bool,
        start: int,
    ) -> past.Tok | past.Op | None | int:
        param: past.Param | past.Op | int | None

        # Encountered whitespace
        idx = start
        idx = self._skip_ws(ln, len(ln), idx)
        shell_exp = True

        if ln[idx] in pint.QUOTES:
            param = self._get_quoted_tok(ln, idx, ln[idx])
        elif ln[idx] in (*pint.LOGI_OPS, *pint.DATA_OPS):
            return None
        elif ln[idx] in pint.CMD_SEPRS:
            return None
        else:
            param = self._get_unquoted_tok(ln, idx)

        if isinstance(param, int):
            return param

        escd_param = self._reslv_esc_chrs(param)
        if isinstance(escd_param, int):
            return escd_param
        if isinstance(escd_param, past.Op):
            return escd_param

        parts, param = escd_param

        final = []
        for part, status in parts:
            # No shell expansion allowed, meaning it was escaped, like "\~"
            # If first parameter, do not perform shell expansion, because I've
            # got no plans of adding direct calls to scripts
            if not status or not do_shell_exp or (isinstance(param, past.Quoted) and param.quote in ("\"", "`")):
                final.append(part)
                continue
            ugen.info(repr(part))
            if part[0] == "~":
                final.append(usr_dir + part[1 :])
                continue
            final.append(part)

        param.val = "".join(final)
        return param

    def _reslv_esc_chrs(
        self,
        param: past.Param | past.Op
    ) -> tuple[list[tuple[str, bool]], past.Param] | past.Op | int:
        parts: list[tuple[str, bool]]

        parts = []
        param_len = len(param.val)
        skip = 0
        escd_hyp = False

        if isinstance(param, past.Op):
            return param

        cur_part = []
        for i, char in enumerate(param.val):
            if skip:
                skip -= 1
                continue
            if char != "\\":
                cur_part.append(char)
                continue
            if i == param_len - 1:
                ugen.err_Q(f"Lone backslash at position {param.start + i}")
                return uerr.ERR_LONE_B_SLASH

            esc_chr_chk_res = pint.ESC_CHR_MAP.get("\\" + param.val[i + 1])
            dir_exp_chr_chk_res = pint.DIR_EXP_CHRS.get("\\" + param.val[i + 1])
            # Basic explanation:
            # Check if next char is in escape char map.
            # Check if next char is in shell expansion map.
            # If it's NOT in BOTH, then append the following char as it is.
            # If it's in shell expansion map, append specially (TBD).
            # If it's in BOTH, escape character resolution is given preference.
            if esc_chr_chk_res is None and dir_exp_chr_chk_res is None:
                cur_part.append(param.val[i + 1])
            elif esc_chr_chk_res is None:
                # Don't append if cur_parts join to form just an empty string
                # Occurs in case of escaped expansion char at the start, or two
                # expansion chars next to each other
                parts.append(("".join(cur_part), True)) if "".join(cur_part) else None
                parts.append((param.val[i + 1], False))
                cur_part = []
            else:
                cur_part.append(esc_chr_chk_res)
            skip += 1

            if not i and param.val[i + 1] == "-":
                escd_hyp = True

        # Add any residual chars, after any escape/expansion chars. Also
        # happens if there were no escape/expansion chars
        if cur_part:
            parts.append(("".join(cur_part), True))

        param.escd_hyp = escd_hyp
        # Quoted
        if isinstance(param, past.Quoted):
            return (parts, param)
        # Unquoted, unless I'm very much mistaken
        else:
            return (parts, param)

    def _get_simp_cmd(
        self,
        ln: str,
        usr_dir: str,
        pth: str,
        start: int
    ) -> past.SimpCmd | int:
        ln_len = len(ln)
        idx = start
        idx = self._skip_ws(ln, ln_len, idx)
        params = []
        while idx < ln_len:
            nxt_param = self._get_nxt_param(ln, usr_dir, pth, do_shell_exp=idx != 0, start=idx)
            if isinstance(nxt_param, int):
                return nxt_param
            # When the next parameter is not related to SimpCmd, e.g. an
            # operator or a command separator
            if nxt_param is None:
                break
            idx = nxt_param.end
            idx = self._skip_ws(ln, ln_len, idx)
            params.append(nxt_param)
        return past.SimpCmd(params)

    def get_cmd_expr(
        self,
        ln: str,
        usr_dir: str,
        pth: str,
        start: int,
    ) -> tuple[past.CmdExpr, int] | int:
        op: past.Op
        ops: list[past.Op]
        simp_cmds: list[past.SimpCmd]

        ln_len = len(ln)
        simp_cmds = []
        ops = []

        # Get the first operand
        simp_cmd = self._get_simp_cmd(ln, usr_dir, pth, start)
        if isinstance(simp_cmd, int):
            return simp_cmd
        simp_cmds.append(simp_cmd)
        idx = simp_cmd.params[-1].end if simp_cmd.params else start
        idx = self._skip_ws(ln, ln_len, idx)

        while idx < ln_len:
            # Get the operator
            curr_ch = ln[idx]
            if curr_ch in pint.LOGI_OPS:
                op = self.LOGI_OP_CHR_NODE_MAP[curr_ch](
                    val=curr_ch,
                    start=idx,
                    end=idx + 1
                )
            elif curr_ch in pint.DATA_OPS:
                op = self.DATA_OP_CHR_NODE_MAP[curr_ch](
                    val=curr_ch,
                    start=idx,
                    end=idx + 1
                )
            else:
                return (past.CmdExpr(simp_cmds, ops), idx)

            ops.append(op)
            # For the operator character
            idx += 1

            # Get each subsequent operand
            idx = self._skip_ws(ln, ln_len, idx)
            simp_cmd = self._get_simp_cmd(ln, usr_dir, pth, idx)
            if isinstance(simp_cmd, int):
                return simp_cmd
            simp_cmds.append(simp_cmd)
            idx = simp_cmd.params[-1].end if simp_cmd.params else idx
            idx = self._skip_ws(ln, ln_len, idx)

        return (past.CmdExpr(simp_cmds, ops), idx)

    def get_cmd_seq(self, ln: str, usr_dir: str, pth: str, start: int = 0):
        cmd_exprs: list[past.CmdExpr]

        ln_len = len(ln)
        idx = start
        cmd_exprs = []

        idx = self._skip_ws(ln, ln_len, idx)
        res = self.get_cmd_expr(ln, usr_dir, pth, start)
        if isinstance(res, int):
            return cmd_exprs
        cmd_expr, idx = res
        cmd_exprs.append(cmd_expr)

        while idx < ln_len:
            idx = self._skip_ws(ln, ln_len, idx)
            curr_ch = ln[idx]
            if curr_ch not in pint.CMD_SEPRS:
                return uerr.ERR_UNRECOGD_CMD_SEPR
            # For the command separator character
            idx += 1

            idx = self._skip_ws(ln, ln_len, idx)
            res = self.get_cmd_expr(ln, usr_dir, pth, idx)
            if isinstance(res, int):
                return cmd_exprs
            cmd_expr, idx = res
            cmd_exprs.append(cmd_expr)

        return past.CmdSeq(cmd_exprs)

    def _skip_ws(self, ln: str, ln_len: int, idx: int) -> int:
        ln_len = len(ln)
        while idx < ln_len and ln[idx].isspace():
            idx += 1
        return idx
