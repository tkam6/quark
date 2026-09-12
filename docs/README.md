# QUARK

A pure-Python, extensible command-line shell with its own parser, execution engine, pipeline system and scripting environment. Quark focuses on simplicity and lightweightness. Holy larp.

See [`CHANGELOG.md`](./CHANGELOG.md) for a history of changes.  
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
To run the shell from source:

```shell
git clone https://gitea.com/vallu/quark.git
cd ./quark/
python3 -m venv ./.venv/
source ./.venv/bin/activate
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

Python 3.13.15 and Nuitka 4.2.1 are required for building the project.  
See the full list of dependencies in `build_reqmts.txt`.

Go to the project root, and build the project with the build script `dev/pc.py`
(assuming the project was already cloned and virtual environment activated):

```shell
python3 -m pip install -r ./build_reqmts.txt
python3 -BOO ./dev/pc.py
```

The help text is not available for the build script as of now, so please go
through the build script source to find out which options and flags are
available.

## Pre-built binaries

For pre-built binaries, check out the
[Releases](https://gitea.com/vallu/quark/releases/) page.

## Configuration

Use the `-h` or `--help` flag with the main program for a list of available
parameters that can passed to the program.

The configuration file, `cfg.py`, is located in the same directory where the
main program is.  
Configuration options available:

```python
ALIASES: dict[str, str] = {}
PTH: tuple[str, ...] = (USR_PY_PTH, *SYS_PY_PTHS, PY_PTH)
PROMPT: str | typing.Callable[[intrpr.internals.IntrprTbl], str] = utils.consts.Defaults.PROMPT
LN_MODE: str = "emacs"
```

## Architecture

The project is divided into several major components:

- **Parser**: tokenises the raw input.
- **Engine** (yes, silly name, I know): evaluates and executes commands.
- **Logger**: the custom logging facility for this project.
- **Utilities**: parts of the project that various other parts use.

## Project status

The project is still in development, and may contain a *lot* of bugs. Use at
your own risk.

## Contributing

This project does not currently accept any contributions.
