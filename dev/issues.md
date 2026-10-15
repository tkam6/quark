# ISSUES

## Core interpreter

### Interpreter engine (src/intrpr/eng.py)

- [DONE BUT NEEDS MORE WORK] (Implemented a workaround) Pipe from an external
command to a built-in command does not work.
- Recursion errors are weird. Like, when the command calls itself repeatedly.
I have no idea what is happening. But design, as of the commit on 25-05-2026,
the return code should be src.utils.err_codes.ERR_RNTIME_ERR. But the child
fails to send the error code through the pipe.
- Error redirects do not work (think it's due to the fact that reporting for
some errors takes place before the redirect stream is set).
- Piping and redirection do not work with aliases.
- Extremely weird error: Do for the first time `ls -l ~/Downloads/;`, and the
error code returned will be 0. Do `ls -l ~/Downloads/; a`, then the error code
will be 200. Removing the unknown command (`a`) will still leave the error code
at 200. `ls -l ~/Downloads/;` after this still leaves the error code at 200.

## Utilities

## Command modules

### src/intrpr/builtin_cmds/help.py

- Difference in padding for different commands. Don't know why.

### src/bin/rf.py

- [IRRELEVANT (STDERR is sent through pipe to parent now), and haven't seen
this issue since] Debug statements get mixed up in the output while executing
the commands in the file. For example, try running a file with the text
"help\n" inside it as `rf ./scr.qrk`. Won't happen every time, but often,
because it seems to be a race between the output text and the debug messages. I
suspect it's due to the output being slow to reach the parent process from the
child process through the pipe.
