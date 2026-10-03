import datetime as dt
import errno
import math
import os
import pathlib as pl
import pwd
import stat
import typing as ty

from src.utils import consts as uconst
from src.utils import err_codes as uerr
from src.utils import gen as ugen

CMD_NM = __name__.split(".")[-1]

HELP = ugen.HelpObj(
    usage=f"{CMD_NM} [flag ...] [opt] [dir ...]",
    summary="List files and directories",
    details=(
        "ARGUMENTS",
        ("none", "List current directory"),
        ("dir", "Directory to list"),
        "OPTIONS",
        ("-p, --padding spaces", "Padding to apply to short listing"),
        "FLAGS",
        ("-a, --all", "Display all (including hidden files)"),
        ("-c, --ctime", "Display CTIME instead of MTIME"),
        ("-e, --case-sensitive", "Case sensitive sort"),
        ("-f, --format-no-tty", "Format output even if stream is not a TTY (assumed 80 characters)"),
        ("-h, --human-readable", "Display human-readable sizes"),
        ("-i, --inode", "Display inode number in long listing"),
        ("-l, --long-list", "Use long listing format"),
        ("-m, --number-inode-links", "Display the number of links to inodes in long listing"),
        ("-N, --no-symlink-symbols", "Suppress symlink indicators"),
        ("-o, --iso", "Use ISO-8601 for dates and times"),
        ("-r, --recursive", "Recursively calculate directory sizes"),
        ("-S, --no-slashes", "Suppress slashes at the end of directory names"),
        ("-t, --almost-all", "Do not list .. and ."),
        ("-u, --unsorted", "Unsorted listing"),
        ("-X, --no-executable-symbols", "Suppress executable indicators")
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=0,
    max_args=float("inf"),
    opts=("-p", "--padding"),
    flags=(
        "-a", "--all",
        "-c", "--ctime",
        "-e", "--case-sensitive",
        "-f", "--format-no-tty",
        "-h", "--human-readable",
        "-i", "--inode",
        "-l", "--long-list",
        "-m", "--number-inode-links",
        "-N", "--no-symlink-symbols",
        "-o", "--iso",
        "-r", "--recursive",
        "-S", "--no-slashes",
        "-t", "--almost-all",
        "-u", "--unsorted",
        "-X", "--no-executable-symbols"
    )
)

PERM_LOOKUP = {
    0: "---",
    1: "--x",
    2: "-w-",
    3: "-wx",
    4: "r--",
    5: "r-x",
    6: "rw-",
    7: "rwx"
}

QUOTES = "\'\""
SP_CHRS = "".join(uconst.SP_CHRS)
WS = " \t\r\n"
BSLASH = "\\"
OTHER = "@*"
QUOTE_STR = QUOTES + SP_CHRS + WS + BSLASH + OTHER


class LsCtx(ty.NamedTuple):
    long_list: bool
    item_visibility: str
    slashes: bool
    symlnk_syms: bool
    xble_syms: bool
    inodes: bool
    num_inode_lnks: bool
    human_rdble: bool
    disp_ctime: bool
    iso: bool
    case_sensi: bool
    unsorted: bool
    recur_dir_szs: bool
    fmt_no_tty: bool
    padding: int


class ItemEntry:
    def __init__(self, pth: str):
        self.path = os.path.realpath(pth)
        self.name = os.path.basename(pth)
        self.actual_name = os.path.basename(self.path)
        self.is_dir = os.path.isdir(self.path)
        self.lstat = lambda: os.lstat(self.path)


class FlEntry(ItemEntry):
    pass


class SplDirEntry(ItemEntry):
    pass


class ShortListEntry(ty.NamedTuple):
    nm: str
    quote: bool
    colour: str
    syms: list[str]


class LongListEntry(ty.NamedTuple):
    nm: str
    typ: str
    owner_perms: str
    grp_perms: str
    others_perms: str
    ctime: str
    mtime: str
    sz: int
    sz_ch: str
    owner_id: int
    owner_nm: str
    inode: int
    num_inode_lnk: int
    syms: list[str]
    quote: bool
    colour: str


class EscWhichObj(ty.NamedTuple):
    quotes: bool = True
    sp_chrs: bool = True
    ws: bool = True
    bslash: bool = True
    other: bool = True

ItemType = FlEntry | SplDirEntry | os.DirEntry

EscWhichObj_empty_inited = EscWhichObj()


def esc_item_nm(
        nm: str,
        esc_which: EscWhichObj = EscWhichObj_empty_inited,
    ) -> str:
    # TODO: Implement regex for this
    str_arr = []
    for ch in nm:
        if (
                (esc_which.quotes and ch in QUOTES and ch != "\'")
                or (esc_which.sp_chrs and ch in SP_CHRS)
                or (esc_which.bslash and ch in BSLASH)
                or (esc_which.other and ch in OTHER)
            ):
            str_arr.append("\\" + ch)
            continue
        str_arr.append(ch)

    if esc_which.ws:
        return (
            "".join(str_arr)
              .replace("\n", "\\n")
              .replace("\r", "\\r")
              .replace("\t", "\\t")
        )
    else:
        return "".join(str_arr)


def get_items(cmd_nm: str, pth: str, ctx: LsCtx) \
        -> tuple[list[tuple[ItemEntry, os.stat_result]], int]:
    err_code = uerr.ERR_ALL_GOOD
    items = []

    # Is a file
    if os.path.isfile(pth):
        fl_obj = FlEntry(pth)
        fl_stat = fl_obj.lstat()
        items.append((fl_obj, fl_stat))

    # Is a directory
    elif os.path.isdir(pth):
        # Case-sensitivity of sorting by name
        sort_fn = lambda e: (e.name if ctx.case_sensi else e.name.lower())
        # Unsorted listing
        if ctx.unsorted:
            iterator = os.scandir(pth)
        else:
            iterator = sorted(os.scandir(pth), key=sort_fn)

        # Special directories, i.e. ".." and "."
        if ctx.item_visibility == "all":
            parent = SplDirEntry("..")
            curr = SplDirEntry(".")
            items.extend((parent, parent.lstat()), (curr, curr.lstat()))

        for i in iterator:
            try:
                # Hidden option filtering
                if (
                    ctx.item_visibility not in ("all", "almost-all")
                    and i.name.startswith(".")
                ):
                    continue
                items.append((i, i.stat(follow_symlinks=False)))
            except OSError as e:
                if e.errno == errno.ENOTCONN:
                    ugen.err(
                        f"Transport endpoint not connected: \"{i.name}\"",
                        nm=cmd_nm
                    )
                    continue
                raise

    # Doesn't exist
    else:
        err_code = uerr.ERR_FL_DIR_404
        ugen.err(f"No such file/directory: \"{pth}\"", nm=cmd_nm)

    return (items, err_code)


def long_list_prn(
    items: list[tuple[pl.Path, os.stat_result]],
    is_tty: bool,
    ctx: LsCtx
) -> None:
    entry: dict[str, ty.Any]

    # pwd.getpwuid(...) calls are real fucking expensive
    uid_cache = {}
    to_prn = []
    max_sz_len = 0
    max_inode_len = 0
    max_num_inode_lnk_len = 0
    max_owner_nm_len = 0

    for (item, item_stat) in items:
        entry = {}
        mode = item_stat.st_mode

        # Item type
        if stat.S_ISDIR(mode):
            typ = "d"
        elif stat.S_ISREG(mode):
            typ = "f"
        elif stat.S_ISLNK(mode):
            typ = "l"
        elif stat.S_ISCHR(mode):
            typ = "c"
        elif stat.S_ISBLK(mode):
            typ = "b"
        elif stat.S_ISFIFO(mode):
            typ = "p"
        elif stat.S_ISSOCK(mode):
            typ = "s"
        else:
            typ = "u"

        # Permissions
        owner_perms = PERM_LOOKUP[(mode >> 6) & 7]
        grp_perms = PERM_LOOKUP[(mode >> 3) & 7]
        others_perms = PERM_LOOKUP[mode & 7]

        # CTIME and MTIME
        fmt_str = r"%Y-%m-%d %H:%M:%S" if ctx.iso else r"%b %d '%y %I.%M%p"
        ctime_timestamp = int(item_stat.st_ctime)
        mtime_timestamp = int(item_stat.st_mtime)
        ctime = dt.datetime.fromtimestamp(ctime_timestamp).strftime(fmt_str)
        mtime = dt.datetime.fromtimestamp(mtime_timestamp).strftime(fmt_str)

        # Size
        sz = item_stat.st_size
        if ctx.recur_dir_szs and typ == "d":
            tmp = pl.Path(item)
            sz = sum(f.stat().st_size for f in tmp.glob("**/*") if f.is_file())
        sz_ch = ""
        if ctx.human_rdble:
            sz_len = len(str(sz))
            if 0 <= sz_len <= 3:
                sz_ch = "B"
            elif 4 <= sz_len <= 6:
                sz //= 10 ** 3
                sz_ch = "kB"
            elif 7 <= sz_len <= 9:
                sz //= 10 ** 6
                sz_ch = "MB"
            elif 10 <= sz_len <= 12:
                sz //= 10 ** 9
                sz_ch = "GB"
            else:
                sz //= 10 ** 12
                sz_ch = "TB"
        max_sz_len = max(max_sz_len, len(str(sz) + sz_ch))

        # Owner ID
        owner_id = item_stat.st_uid
        if owner_id not in uid_cache:
            try:
                uid_cache[owner_id] = pwd.getpwuid(owner_id).pw_name
            except KeyError:
                uid_cache[owner_id] = "?"
        owner_nm = uid_cache[owner_id]
        max_owner_nm_len = max(max_owner_nm_len, len(owner_nm))

        # Inode number
        inode = item_stat.st_ino
        num_inode_lnk = item_stat.st_nlink
        max_inode_len = max(max_inode_len, len(str(inode)))
        max_num_inode_lnk_len = max(
            max_num_inode_lnk_len,
            len(str(num_inode_lnk))
        )

        nm = item.name
        colour = ""
        syms = []
        quote = False
        if is_tty:
            # Quote names with special characters
            if [ch for ch in nm if ch in QUOTE_STR]:
                nm = esc_item_nm(nm, esc_which=EscWhichObj(sp_chrs=False))
                quote = True
            # Colours
            if typ == "d":
                colour = ugen.S.green_4
            else:
                colour = ugen.S.blue_4
            # Item type symbols
            if ctx.slashes and typ == "d":
                syms.append(os.sep)
            elif ctx.symlnk_syms and typ == "l":
                syms.append(ugen.S.fmt("@", is_tty, ugen.S.magenta_4))
            if ctx.xble_syms and typ != "d" and os.access(item.path, os.X_OK):
                syms.append(ugen.S.fmt("*", is_tty, ugen.S.cyan_4))

        entry = LongListEntry(
            nm=nm,
            typ=typ,
            owner_perms=owner_perms,
            grp_perms=grp_perms,
            others_perms=others_perms,
            ctime=ctime,
            mtime=mtime,
            sz=sz,
            sz_ch=sz_ch,
            owner_id=owner_id,
            owner_nm=owner_nm,
            inode=inode,
            num_inode_lnk=num_inode_lnk,
            syms=syms,
            quote=quote,
            colour=colour
        )
        to_prn.append(entry)

    # Print data obtained
    for i in to_prn:
        sz_w_ch = str(i.sz) + i.sz_ch
        item_perms = i.owner_perms + i.grp_perms + i.others_perms
        c_or_mtime = str(i.ctime) if ctx.disp_ctime else str(i.mtime)
        padded_inode = str(i.inode).rjust(max_inode_len)
        padded_num_inode_lnk = (
            str(i.num_inode_lnk).rjust(max_num_inode_lnk_len)
        )
        coloured_nm = ugen.S.fmt(i.nm, is_tty, i.colour)
        ugen.write(
            i.typ
            + " " + item_perms
            + (("  " + padded_inode) if ctx.inodes else "")
            + (("  " + padded_num_inode_lnk) if ctx.num_inode_lnks else "")
            + "  " + i.owner_nm.ljust(max_owner_nm_len)
            + "  " + c_or_mtime
            + "  " + sz_w_ch.rjust(max_sz_len)
            + "  " + (
                ("\"" if i.quote else " ")
                + coloured_nm
                + ("\"" if i.quote else "")
            )
            + "".join(i.syms)
            + "\n"
        )


def short_list_prn(
    items: list[tuple[pl.Path, os.stat_result]],
    is_tty: bool,
    term_sz: os.terminal_size,
    ctx: LsCtx
) -> None:
    # ALL HAIL THE WORST ls ALGORITHM KNOWN TO MAN!
    fmted_items = []
    fmted_items_app = fmted_items.append
    max_len = 0
    padding = ctx.padding

    for (item, item_stat) in items:
        nm = item.name
        mode = item_stat.st_mode
        quote = False
        syms = []
        colour = ""

        if is_tty:
            if [ch for ch in item.name if ch in QUOTE_STR]:
                quote = True
            # Quote item if contains special chars
            if quote:
                nm = esc_item_nm(nm, esc_which=EscWhichObj(sp_chrs=False))
            is_dir = stat.S_ISDIR(mode)
            # Colours
            if is_dir:
                colour = ugen.S.green_4
            else:
                colour = ugen.S.blue_4
            # Item type symbols
            if ctx.slashes and is_dir:
                syms.append(os.sep)
            if ctx.symlnk_syms and stat.S_ISLNK(mode):
                syms.append(ugen.S.fmt("@", is_tty, ugen.S.magenta_4))
            if ctx.xble_syms and not is_dir and os.access(item.path, os.X_OK):
                syms.append(ugen.S.fmt("*", is_tty, ugen.S.cyan_4))

        entry = ShortListEntry(nm=nm, quote=quote, colour=colour, syms=syms)
        fmted_items_app(entry)
        # This is not the most efficient for spacing... but I don't give a damn
        # Length of name + length of quotes (if present) + length of symbols
        # + length of spaces at the front and end of the entry (if any item
        # of the entry's column contains quotes)
        max_len = max(max_len, len(nm) + (2 if quote else 0) + len(syms) + 2)

    if is_tty or ctx.fmt_no_tty:
        # Assume 80-character terminal if errors are encountered when
        # determining number of columns
        cols_avail = 80 if ctx.fmt_no_tty else term_sz.columns
        max_cols = cols_avail // (max_len + padding)
        if max_cols <= 0:
            max_cols = 1

        to_prn = []
        col_props = [{"len": 0, "quote": False} for _ in range(max_cols)]
        num_lns = math.ceil(len(fmted_items) / max_cols)
        for i in range(num_lns):
            fmted_item_slice = fmted_items[i * max_cols : (i + 1) * max_cols]
            to_prn.append(fmted_item_slice)
            for idx, item in enumerate(fmted_item_slice):
                col_props[idx]["len"] = max(
                    col_props[idx]["len"],
                    # Length of item name + length of quotes (if present)
                    # + length of symbols to be displayed
                    len(item.nm) + (2 if item.quote else 0) + len(item.syms)
                )
                col_props[idx]["quote"] = col_props[idx]["quote"] or item.quote

        for items in to_prn:
            padded_items = []
            for j, item in enumerate(items):
                # NOTE: Uncomment to tighten padding according to col max lens
                # padded_items.append(ugen.ljust(item, col_props[j]["len"]))
                nm = (
                    ("\"" if item.quote else (" " if col_props[j]["quote"] else ""))
                    + ugen.S.fmt(item.nm, is_tty, item.colour)
                    + ("\"" if item.quote else "")
                    + "".join(item.syms)
                    + (" " if col_props[j]["quote"] else "")
                )
                padded_items.append(ugen.ljust(nm, max_len))
            ugen.write((" " * padding).join(padded_items) + "\n")

    else:
        for i in fmted_items:
            ugen.write(i.nm + "\n")


def run(data: ugen.CmdData) -> int:
    err_code = uerr.ERR_ALL_GOOD
    long_list = False
    inodes = False
    num_inode_lnks = False
    human_rdble = False
    disp_ctime = False
    item_visibility = "normal"
    case_sensi = False
    unsorted = False
    iso = False
    fmt_no_tty = False
    symlnk_syms = True
    xble_syms = True
    slashes = True
    recur_dir_szs = False
    padding = 2

    for flag in data.flags:
        if flag in ("-l", "--long-list"):
            long_list = True
        elif flag in ("-i", "--inode"):
            inodes = True
        elif flag in ("-m", "--number-inode-links"):
            num_inode_lnks = True
        elif flag in ("-h", "--human-readable"):
            human_rdble = True
        elif flag in ("-c", "--ctime"):
            disp_ctime = True
        elif flag in ("-a", "--all"):
            item_visibility = "all"
        elif flag in ("-e", "--case-sensitive"):
            case_sensi = True
        elif flag in ("-u", "--unsorted"):
            unsorted = True
        elif flag in ("-o", "--iso"):
            iso = True
        elif flag in ("-r", "--recursive"):
            recur_dir_szs = True
        elif flag in ("-f", "--format-no-tty"):
            fmt_no_tty = True
        elif flag in ("-t", "--almost-all"):
            item_visibility = "almost-all"
        elif flag in ("-S", "--no-slashes"):
            slashes = False
        elif flag in ("-N", "--no-symlink-symbols"):
            symlnk_syms = False
        elif flag in ("-X", "--no-executable-symbols"):
            xble_syms = False

    for opt, val in data.opts.items():
        if opt in ("-p", "--padding"):
            try:
                int(val)
            except ValueError:
                ugen.err(
                    f"Cannot cast to int (option {opt}): '{val}'",
                    nm=data.cmd_nm
                )
                return uerr.ERR_CANT_CAST_VAL
            padding = int(val)

    ctx = LsCtx(
        long_list=long_list,
        item_visibility=item_visibility,
        symlnk_syms=symlnk_syms,
        xble_syms=xble_syms,
        slashes=slashes,
        inodes=inodes,
        num_inode_lnks=num_inode_lnks,
        human_rdble=human_rdble,
        disp_ctime=disp_ctime,
        iso=iso,
        case_sensi=case_sensi,
        unsorted=unsorted,
        recur_dir_szs=recur_dir_szs,
        fmt_no_tty=fmt_no_tty,
        padding=padding
    )

    # No arguments
    if not data.args:
        pth = os.path.expanduser("./")
        try:
            items, err_code = get_items(
                data.cmd_nm,
                pth,
                ctx
            )
        # FileNotFoundError, PermissionError will be caused by race conditions
        except FileNotFoundError:
            ugen.err(f"No such file/directory: \"{pth}\"", nm=data.cmd_nm)
            return uerr.ERR_FL_DIR_404
        except PermissionError:
            ugen.err(f"Access denied: \"{pth}\"", nm=data.cmd_nm)
            return uerr.ERR_PERM_DENIED
        except OSError as e:
            ugen.err(f"OS error; {e.strerror}", nm=data.cmd_nm)
            return uerr.ERR_OS_ERR

        if not err_code:
            ugen.write(ugen.S.fmt("./", data.is_tty, ugen.S.green_4) + "\n")
            if long_list:
                long_list_prn(items, is_tty=data.is_tty, ctx=ctx)
            else:
                short_list_prn(
                    items,
                    is_tty=data.is_tty,
                    term_sz=data.term_sz,
                    ctx=ctx
                )

    # Yes arguments
    else:
        for arg in data.args:
            tmp_err_code = uerr.ERR_ALL_GOOD
            try:
                items, tmp_err_code = get_items(
                    data.cmd_nm,
                    os.path.expanduser(arg),
                    ctx=ctx
                )
            # FileNotFoundError, PermissionError will be due to race conditions
            except FileNotFoundError:
                tmp_err_code = uerr.ERR_FL_DIR_404
                ugen.err(f"No such file/directory: \"{arg}\"", nm=data.cmd_nm)
            except PermissionError:
                tmp_err_code = uerr.ERR_PERM_DENIED
                ugen.err(f"Access denied: \"{arg}\"", nm=data.cmd_nm)
            except OSError as e:
                tmp_err_code = uerr.ERR_OS_ERR
                ugen.err(f"OS error; {e.strerror}", nm=data.cmd_nm)

            # Errors encountered when "getting" items for current argument
            if tmp_err_code:
                err_code = err_code or tmp_err_code
                continue
            ugen.write(ugen.S.fmt(arg, data.is_tty, ugen.S.green_4) + "\n")
            if long_list:
                long_list_prn(items, is_tty=data.is_tty, ctx=ctx)
            else:
                short_list_prn(
                    items,
                    is_tty=data.is_tty,
                    term_sz=data.term_sz,
                    ctx=ctx
                )

    return err_code
