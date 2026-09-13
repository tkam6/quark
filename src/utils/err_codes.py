iota_cntr = 0
def iota(set_val: int | None = None):
    global iota_cntr
    if set_val is not None:
        iota_cntr = set_val
    tmp = iota_cntr
    iota_cntr += 1
    return tmp


ERR_ALL_GOOD = iota(0)
ERR_FALSE = iota()
# MAIN PROGRAM
ERR_MP_EXPD_VAL_OPT = iota(2)
ERR_MP_UNK_TOK = iota()
ERR_MP_INV_VAL = iota()
ERR_MP_BEAUTY_OVERLD = iota()

ERR_UNK_ERR = iota(10)
ERR_UNK_FATAL = iota()

ERR_BEAUTY_OVERLD = iota(50)

# PARSING ERRORS
ERR_NO_CLOSING_QUOTE = iota(100)
ERR_LONE_B_SLASH = iota()
ERR_UNRECOGD_CMD_SEPR = iota()

# INTERPRETER ERRORS
ERR_BAD_CMD = iota(200)
ERR_INV_CMD = iota()
ERR_NO_CMD_FN = iota()
ERR_NO_CMD_SPEC = iota()
ERR_NO_HELP_OBJ = iota()
ERR_UNCALLABLE_CMD_FN = iota()
ERR_INV_NUM_PARAMS = iota()
ERR_INV_CMD_SPEC = iota()
ERR_INV_HELP_OBJ = iota()
ERR_CMD_SYN_ERR = iota()
ERR_CANT_LD_CMD_MOD = iota()
ERR_CANT_FORK_PROC = iota()
ERR_EXPD_VAL_OPT = iota()
ERR_EXPD_SUB_CMD = iota()
ERR_INV_SUB_CMD = iota()
ERR_INSUFF_ARGS = iota()
ERR_UNEXPD_ARGS = iota()
ERR_INV_OPTS_FLAGS = iota()
ERR_RECUR_ERR = iota()
ERR_CMD_RNTIME_ERR = iota()
ERR_CMD_SYS_EXIT = iota()
ERR_UNPACK_FAIL = iota()
ERR_CMD_RETD_NON_INT = iota()
ERR_RET_INT_TOO_LARGE = iota()
ERR_KB_INTERR = iota()
ERR_CMD_STATUS_UNPACK = iota()
ERR_UNEXPD_PARAM_STDOUT_REDIRN = iota()
ERR_UNEXPD_PARAM_STDERR_REDIRN = iota()
ERR_EXPD_FLNM_STDOUT_REDIRN = iota()
ERR_EXPD_PARAM_RT_OP = iota()
ERR_TOO_MANY_OPEN_FLS = iota()
ERR_NOT_IMPLMTD = iota()

# ENVIRONMENT VARIABLE CODES
ERR_ENV_VAR_INV_TYP = iota(300)
ERR_ENV_VAR_INV_NM = iota()
ERR_ENV_UNK_VAR = iota()
ERR_CORRUPTED_ENV_TBL = iota()

# COMMON COMMAND ERRORS
ERR_INV_USAGE = iota(400)
ERR_OS_ERR = iota()
ERR_FL_404 = iota()
ERR_DIR_404 = iota()
ERR_FL_DIR_404 = iota()
ERR_FL_EXISTS = iota()
ERR_DIR_EXISTS = iota()
ERR_FL_DIR_EXISTS = iota()
ERR_IS_A_FL = iota()
ERR_IS_A_DIR = iota()
ERR_NOT_A_FL = iota()
ERR_NOT_A_DIR = iota()
ERR_NO_SPACE_ON_DEV = iota()
ERR_PERM_DENIED = iota()
ERR_EXPD_STDIN_OR_ARGS = iota()
ERR_CANT_CAST_VAL = iota()
ERR_INV_OPT_FMT = iota()
ERR_INV_VAL_OPT = iota()
ERR_DECODE_ERR = iota()
ERR_INT_OVERFLOW = iota()

# CONFIG ERRORS
ERR_CFG_INV_TYP = iota(500)

# TMP
ERR_PLACEHOLDER = iota(10000)
