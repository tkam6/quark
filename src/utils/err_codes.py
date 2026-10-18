import enum

iota_cntr = 0
def iota(set_val: int | None = None):
    global iota_cntr
    if set_val is not None:
        iota_cntr = set_val
    tmp = iota_cntr
    iota_cntr += 1
    return tmp


class RC(enum.IntEnum):
    ALL_GOOD = enum.auto(0)
    FALSE = enum.auto()

    # MAIN PROGRAM
    MP_EXPD_VAL_OPT = enum.auto(2)
    MP_UNK_TOK = enum.auto()
    MP_INV_VAL = enum.auto()
    MP_BEAUTY_OVERLD = enum.auto()

    UNK_ERR = enum.auto(10)
    UNK_FATAL = enum.auto()

    BEAUTY_OVERLD = enum.auto(50)

    # PARSING ERRORS
    NO_CLOSING_QUOTE = enum.auto(100)
    LONE_B_SLASH = enum.auto()
    UNRECOGD_CMD_SEPR = enum.auto()

    # INTERPRETER ERRORS
    BAD_CMD = enum.auto(200)
    INV_CMD = enum.auto()
    NO_CMD_FN = enum.auto()
    NO_CMD_SPEC = enum.auto()
    NO_HELP_OBJ = enum.auto()
    UNCALLABLE_CMD_FN = enum.auto()
    INV_NUM_PARAMS = enum.auto()
    INV_CMD_SPEC = enum.auto()
    INV_HELP_OBJ = enum.auto()
    CMD_SYN_ERR = enum.auto()
    CANT_LD_CMD_MOD = enum.auto()
    CANT_FORK_PROC = enum.auto()
    EXPD_VAL_OPT = enum.auto()
    EXPD_SUB_CMD = enum.auto()
    INV_SUB_CMD = enum.auto()
    INSUFF_ARGS = enum.auto()
    UNEXPD_ARGS = enum.auto()
    INV_OPTS_FLAGS = enum.auto()
    RECUR_ERR = enum.auto()
    CMD_RNTIME_ERR = enum.auto()
    CMD_SYS_EXIT = enum.auto()
    UNPACK_FAIL = enum.auto()
    CMD_RETD_NON_INT = enum.auto()
    RET_INT_TOO_LARGE = enum.auto()
    KB_INTERR = enum.auto()
    CMD_STATUS_UNPACK = enum.auto()
    UNEXPD_PARAM_STDOUT_REDIRN = enum.auto()
    UNEXPD_PARAM_STDREDIRN = enum.auto()
    EXPD_FLNM_STDOUT_REDIRN = enum.auto()
    EXPD_PARAM_RT_OP = enum.auto()
    TOO_MANY_OPEN_FLS = enum.auto()
    NOT_IMPLMTD = enum.auto()

    # ENVIRONMENT VARIABLE CODES
    ENV_VAR_INV_TYP = enum.auto(300)
    ENV_VAR_INV_NM = enum.auto()
    ENV_UNK_VAR = enum.auto()
    CORRUPTED_ENV_TBL = enum.auto()

    # COMMON COMMAND ERRORS
    INV_USAGE = enum.auto(400)
    OS_ERR = enum.auto()
    FL_404 = enum.auto()
    DIR_404 = enum.auto()
    FL_DIR_404 = enum.auto()
    FL_EXISTS = enum.auto()
    DIR_EXISTS = enum.auto()
    FL_DIR_EXISTS = enum.auto()
    IS_A_FL = enum.auto()
    IS_A_DIR = enum.auto()
    NOT_A_FL = enum.auto()
    NOT_A_DIR = enum.auto()
    NO_SPACE_ON_DEV = enum.auto()
    PERM_DENIED = enum.auto()
    EXPD_STDIN_OR_ARGS = enum.auto()
    CANT_CAST_VAL = enum.auto()
    INV_OPT_FMT = enum.auto()
    INV_VAL_OPT = enum.auto()
    DECODE_ERR = enum.auto()
    INT_OVERFLOW = enum.auto()

    # CONFIG ERRORS
    CFG_INV_TYP = enum.auto(500)

    # TMP
    PLACEHOLDER = enum.auto(10000)
