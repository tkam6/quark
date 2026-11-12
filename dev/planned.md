# PLANNED

## Entry point

- Implement more powerful tab-completion. Context-aware, etc.

## Parser

### Parser engine (src/intrpr/eng.py)

- Implement globbing.

## Core interpreter

### Interpreter engine (src/intrpr/eng.py)

- Test piping, because it uses StringIO. Test if StringIO fails on large data
volumes. If yes, use temporary files to overcome the restriction in size of
io.StringIO buffers.
- Argument, option and flag classification: need to include entries in the
command spec to define valid flags for individual subcommands.

### General utils and command API (src/utils/gen.py)

- [DONE, NEEDS IMPROVEMENT] Implement tab completion.
- Implement a way to identify the origin of the log message (the function in
immediately before on stack, or the filename the log message originates from).

## Command modules

### ls (src/bin/ls.py)

- Dynamically change the column lengths to maximise efficiency in using the
available space. Like, after calculating the number of columns, re-adjust the
column lengths after individual column lengths are found. Or something of that
sort.

### sys (src/bin/sys.py)

- Create this command, and integrate system information, like hostname and the
sort, into this command.

### help (src/intrpr/builtin_cmds/help.py)

- Need to come up with a better help system. Like, commands should be written in
such a way that arguments, options or flags that are not undocumented in the
help message should be clearly visible to the developer. For that, I need to
first develop a system of defining arguments, options and flags in a command,
like I have the three compulsory attributes HELP, CMD_SPEC and run. And
CMD_SPEC and HELP should obtain info from these, as well as other checks and
other things with the arguments and options and flags. Another attribute can be
used to store the necessary descriptions of arguments, options and flags. I
will not be implementing this right now, but will do so in the future.
