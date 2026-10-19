# PLANNED

## Entry point

- Implement more powerful tab-completion. Context-aware, etc.

## Parser

### Parser engine (src/intrpr/eng.py)

- Implement globbing.
- Add indices to indicate the order of arguments and options and flags. The
indices should be "global"; meaning, it must include all args, opts and flags
in a continuous array of numbers. Don't implement it as three different arrays
of numbers! We need continuous for commands like `sys`.

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
