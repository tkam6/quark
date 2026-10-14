import os
import platform as pf
import re
import typing as ty

from src.intrpr import internals as iint
from src.utils import consts as uconst
from src.utils import gen as ugen

if ty.TYPE_CHECKING:
    import src.intrpr.eng as ieng


def reslv_prompt_var(
    intrpr_obj: "ieng.Intrpr",
    prompt: ty.Callable[[iint.IntrprTbl], ty.Any] | str,
) -> str:
    dflt_prompt = uconst.Defaults.PROMPT(intrpr_obj.intrpr_vars)

    if isinstance(prompt, str):
        prompt_str = prompt
    elif callable(prompt):
        try:
            prompt_str = prompt(intrpr_obj.intrpr_vars)
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
    intrpr_obj: "ieng.Intrpr",
    prompt_obj: ty.Callable[[iint.IntrprTbl], ty.Any] | str | None,
) -> str:
    # Pretty bad design, I guess, handling the None case for variable
    # prompt in this method, but I don't want to clutter up the main file
    if prompt_obj is None:
        prompt_obj = uconst.Defaults.PROMPT

    prompt = reslv_prompt_var(intrpr_obj, prompt_obj)
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
            if intrpr_obj._last_bad_prompt_obj != prompt_obj:
                ugen.warn_Q(
                    "Lone '!' in prompt variable; falling back to default prompt",
                )
                intrpr_obj._last_bad_prompt_obj = prompt_obj
            return reslv_prompt(intrpr_obj, uconst.Defaults.PROMPT)

        nxt_chr = prompt[i + 1]

        # Condensed path
        if nxt_chr == "p":
            cwd_conden = re.sub(
                f"^{re.escape(str(intrpr_obj.usr_dir))}",
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
                f"^{intrpr_obj.usr_dir}",
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
            final_prompt += intrpr_obj.usernm
            skip += 1
            continue
        elif nxt_chr == "U":
            final_prompt += intrpr_obj.uid
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
            if intrpr_obj.is_usr_root:
                final_prompt += "%"
            else:
                final_prompt += "$"
            skip += 1
            continue
        elif nxt_chr == "?":
            final_prompt += str(intrpr_obj.intrpr_vars["LAST_RET"])
            skip += 1
            continue
        # Literal '!'
        elif nxt_chr == "!":
            final_prompt += "!"
            skip += 1
            continue
        else:
            # Issue warning only once
            if intrpr_obj._last_bad_prompt_obj != prompt_obj:
                ugen.warn_Q(
                    f"Invalid prompt substitution symbol: '!{nxt_chr}'; falling back to default prompt"
                )
                intrpr_obj._last_bad_prompt_obj = prompt_obj
            return reslv_prompt(intrpr_obj, uconst.Defaults.PROMPT)

    return final_prompt
