# QUARK

A pure-Python, extensible command-line shell with its own parser, execution engine, pipeline system and scripting environment. Quark focuses on simplicity and lightweightness. Holy larp.

See [`docs/`](../docs/) for detailed documentation on modules and internals.  
See [`dev/`](../dev/) for development notes and plans.  
See [`dev/planned.md`](../dev/planned.md) for future development plans and
ideas.  
See [`dev/issues.md`](../dev/issues.md) for bugs and issues in the project.

## Why Quark?

Quark started off as a project for myself to learn how shells work. That is why instead of wrapping an existing shell, everything is implemented from scratch. You name it: parser, command execution model, pipelines, environment handling.

You know, the goal is not to replace Bash or Zsh or other mature shells. Rather, this is merely an experiment in language and shell design and architecture, and interpreters.

## Highlights

- Written from scratch depending only on the standard library to run
- Custom lexer and parser
- Custom pipelines
- Small and fast

## Features

- Interactive command-line interface
- Built-in and external commands
- Extensible command system
- Live reload
- Powerful and large scripting system (Python)
- Alias support
- Interpreter and environment variable system
- Piping and redirection
- Command history
- Tab completion
- Configurable

## Quick start: running from source

Python 3.13 or later is required for running the program from source.  
To run the shell from source, clone this repository, `cd` into it, and:

```shell
python3 -m venv ./.venv/
. ./.venv/bin/activate
python3 -m pip install -e ./
python3 -BOO ./src/main.py
```

Use the `-h` flag with the main program for the help text.  
Example commands:

```
help -a
ls -la
cd ../
echo -s , hello world
```

## Building from source

Python 3.13.16 and Nuitka 4.2.2 (latest Nuitka version causes a segfaults for
some reason) are required for building the project.  
See the full list of dependencies in `requirements-buildtime.txt`.

To build this project, clone this repository, `cd` into it, and use the build
script `dev/pc.py`:

```shell
python3 -m venv ./.venv/
. ./.venv/bin/activate
python3 -m pip install -e ./
python3 -m pip install -r ./requirements-buildtime.txt
python3 -BOO ./dev/pc.py
```

Help text is not available for the build script as of now, so go through the
build script source to find out what options and flags are available.

## Pre-built binaries

It's best to build it yourself.

## Configuration

Use the `-h` or `--help` flag with the main program for a list of available
parameters that can passed to the program.

The configuration file, `cfg.py`, is located in the same directory where the
main program is.  
Configuration options available:

```python
# The comments are examples
# {"ls": "ls -a", "cat": "prn", ...}
ALIASES: dict[str, str] = {}
# ("@bin/special", "~/py", ...)
PTH: tuple[str, ...] = (USR_PY_PTH, *SYS_PY_PTHS, PY_PTH)
# PROMPT = some_function
# PROMPT = "!u@!h !p $"
PROMPT: str | typing.Callable[[intrpr.internals.IntrprTbl], str] = utils.consts.Defaults.PROMPT
# Accepted values: "emacs", "vi", "raw"
LN_MODE: str = "emacs"
```

## Architecture

See the [Architecture](dev/archi.mod) file.

## Project status

The project is still very early in development, and may contain a *lot* of
bugs. Use at your own risk. Or better, don't use it at all.

## Contributing

This project does not currently accept any contributions.
