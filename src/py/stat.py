import datetime as dt
import json
import pathlib as pl
import pwd
import stat

from src.utils import err_codes as uerr
from src.utils import gen as ugen

CMD_NM = __name__.split(".")[-1]

HELP = ugen.HelpObj(
    usage=f"{CMD_NM} [opt] [flag ...] item [...]",
    summary="Query item information",
    details=(
        "ARGUMENTS",
        ("item", "Item to query information for"),
        "OPTIONS",
        (
            "--json-indent",
            "Number of spaces to indent when writing JSON; int expected"
        ),
        "FLAGS",
        ("-i, --iso", "Follow the ISO date and time convention"),
        ("-j, --write-json", "Write JSON output"),
        ("-l, --follow-symlinks", "Follow symlinks"),
        ("-p, --short-permissions", "Display short permission string (rwx)"),
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=1,
    max_args=float("inf"),
    opts=("--json-indent",),
    flags=(
        "-i", "--iso",
        "-j", "--write-json",
        "-l", "--follow-symlinks",
        "-p", "--short-permissions"
    )
)

PERM_LOOKUP_LONG = {
    0: "none",
    1: "execute",
    2: "write",
    3: "write, execute",
    4: "read",
    5: "read, execute",
    6: "read, write",
    7: "read, write, execute"
}
PERM_LOOKUP_NORM = {
    0: "---",
    1: "--x",
    2: "-w-",
    3: "-wx",
    4: "r--",
    5: "r-x",
    6: "rw-",
    7: "rwx"
}


def run(data: ugen.CmdData) -> int:
    err_code = uerr.ERR_ALL_GOOD
    len_args = len(data.args)
    json_indent = 2
    write_json = False
    flw_symlnks = False
    iso = False
    short_perms = False

    for flag in data.flags:
        if flag in ("-j", "--write-json"):
            write_json = True
        elif flag in ("-l", "--follow-symlinks"):
            flw_symlnks = True
        elif flag in ("-i", "--iso"):
            iso = True
        elif flag in ("-p", "--short-permissions"):
            short_perms = True

    for opt in data.opts:
        val = data.opts[opt]
        if opt == "--json-indent":
            try:
                json_indent = int(val)
            except ValueError:
                ugen.err(
                    f"Cannot cast to int for '{opt}': '{val}'",
                    nm=data.cmd_nm
                )
                return uerr.ERR_CANT_CAST_VAL

    if iso or write_json:
        fmt_str = r"%Y-%m-%d %H:%M:%S"
    else:
        fmt_str = r"%b %d '%y %I.%M%p"

    if data.is_tty:
        # Remember: Change max_len when adding columns bigger than current value!
        max_len = 24
    else:
        max_len = 0

    has_dir = hasattr(stat, "S_ISDIR")
    has_reg = hasattr(stat, "S_ISREG")
    has_lnk = hasattr(stat, "S_ISLNK")
    has_chr = hasattr(stat, "S_ISCHR")
    has_blk = hasattr(stat, "S_ISBLK")
    has_fifo = hasattr(stat, "S_ISFIFO")
    has_sock = hasattr(stat, "S_ISSOCK")
    has_door = hasattr(stat, "S_ISDOOR")
    has_port = hasattr(stat, "S_ISPORT")
    has_wht = hasattr(stat, "S_ISWHT")

    # Headers, padded
    nm_head = ugen.ljust("item name:", max_len)
    pth_head = ugen.ljust("full path:", max_len)
    inode_num_lnks_head = ugen.ljust("inode [number of links]:", max_len)
    typ_typ_chr_head = ugen.ljust('type [type character]:', max_len)
    sz_head = ugen.ljust("size:", max_len)
    owner_nm_uid_head = ugen.ljust("owner name [UID]:", max_len)
    owner_perms_head = ugen.ljust("owner permissions:", max_len)
    grp_perms_head = ugen.ljust("group permissions:", max_len)
    others_perms_head = ugen.ljust("others permissions:", max_len)
    last_access_head = ugen.ljust("last access:", max_len)
    last_modify_head = ugen.ljust("last modify:", max_len)
    last_metadata_chg_head = ugen.ljust("last metadata change:", max_len)

    # If JSON output, then print an "array start" symbol, i.e. a '['
    if write_json:
        ugen.write("[\n")

    for idx, arg in enumerate(data.args):
        pth_obj = pl.Path(arg).absolute()
        try:
            item_stat = pth_obj.stat(follow_symlinks=flw_symlnks)
        except FileNotFoundError:
            err_code = err_code or uerr.ERR_FL_DIR_404
            ugen.err(f"Cannot locate item: \"{arg}\"", nm=data.cmd_nm)
            continue
        except PermissionError:
            err_code = err_code or uerr.ERR_PERM_DENIED
            ugen.err(f"Access denied: \"{arg}\"", nm=data.cmd_nm)
            continue
        except OSError as e:
            err_code = err_code or uerr.ERR_OS_ERR
            ugen.err(f"OS error; {e.strerror}", nm=data.cmd_nm)
            continue

        mode = item_stat.st_mode

        if has_dir and stat.S_ISDIR(mode):
            typ = "directory"
            typ_ch = "d"
        elif has_reg and stat.S_ISREG(mode):
            typ = "regular file"
            typ_ch = "f"
        elif has_lnk and stat.S_ISLNK(mode):
            typ = "symbolic link"
            typ_ch = "l"
        elif has_chr and stat.S_ISCHR(mode):
            typ = "character special device file"
            typ_ch = "c"
        elif has_blk and stat.S_ISBLK(mode):
            typ = "block special device file"
            typ_ch = "b"
        elif has_fifo and stat.S_ISFIFO(mode):
            typ = "named pipe"
            typ_ch = "p"
        elif has_sock and stat.S_ISSOCK(mode):
            typ = "socket"
            typ_ch = "s"
        elif has_door and stat.S_ISDOOR(mode):
            typ = "door"
            typ_ch = "d"
        elif has_port and stat.S_ISPORT(mode):
            typ = "event port"
            typ_ch = "e"
        elif has_wht and stat.S_ISWHT(mode):
            typ = "whiteout"
            typ_ch = "w"
        else:
            typ = "unknown"
            typ_ch = "u"

        # Collect data from stat and mode
        nm = pth_obj.name
        pth = str(pth_obj)
        inode = item_stat.st_ino
        num_inode_lnks = item_stat.st_nlink
        owner_uid = item_stat.st_uid
        owner_gid = item_stat.st_gid
        sz = item_stat.st_size
        ctime = dt.datetime.fromtimestamp(item_stat.st_ctime).strftime(fmt_str)
        mtime = dt.datetime.fromtimestamp(item_stat.st_mtime).strftime(fmt_str)
        atime = dt.datetime.fromtimestamp(item_stat.st_atime).strftime(fmt_str)
        if short_perms or write_json:
            perm_lookup = PERM_LOOKUP_NORM
        else:
            perm_lookup = PERM_LOOKUP_LONG
        owner_perms = perm_lookup[(mode >> 6) & 7]
        grp_perms = perm_lookup[(mode >> 3) & 7]
        others_perms = perm_lookup[mode & 7]
        try:
            owner_usrnm = pwd.getpwuid(owner_uid).pw_name
        except KeyError:
            owner_usrnm = "?"

        if write_json:
            data_dict = {
                "nm": nm,
                "pth": pth,
                "inode": inode,
                "num_inode_lnks": num_inode_lnks,
                "owner_uid": owner_uid,
                "owner_gid": owner_gid,
                "owner_usrnm": owner_usrnm,
                "owner_perms": owner_perms,
                "grp_perms": grp_perms,
                "others_perms": others_perms,
                "sz": sz,
                "ctime": ctime,
                "atime": atime,
                "mtime": mtime
            }
            try:
                dict_str_arr = json.dumps(
                    data_dict,
                    indent=json_indent
                ).splitlines()
            except OverflowError:
                ugen.err(f"Indent value too large: {json_indent}")
                err_code = err_code or uerr.ERR_INT_OVERFLOW
                return err_code
            ugen.write(
                # No idea why this first indent is needed. It should've been
                # covered in "\n" + " " * json_indent itself, but... it isn't
                " " * json_indent
                + ("\n" + " " * json_indent).join(dict_str_arr)
                + (",\n" if idx < len_args - 1 else "\n")
            )

        else:
            # WRITE IT!
            ugen.write("\n".join((
                ugen.S.fmt(arg, data.is_tty, ugen.S.cyan_4),
                f"{nm_head} {nm}",
                f"{pth_head} {pth}",
                f"{inode_num_lnks_head} {inode} [{num_inode_lnks}]",
                f"{typ_typ_chr_head} {typ} [{typ_ch}]",
                f"{sz_head} {sz}",
                f"{owner_nm_uid_head} {owner_usrnm} [{owner_uid}]",
                f"{owner_perms_head} {owner_perms}",
                f"{grp_perms_head} {grp_perms}",
                f"{others_perms_head} {others_perms}",
                f"{last_access_head} {atime}",
                f"{last_modify_head} {mtime}",
                f"{last_metadata_chg_head} {ctime}"
            )) + "\n")

    # Finally, if JSON output, print the "array end" symbol, i.e. a ']'
    if write_json:
        ugen.write("]\n")

    return err_code
