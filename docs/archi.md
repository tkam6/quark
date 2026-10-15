# INTERPRETER ARCHITECTURE

## Control flow

```
Main program (user input)
   |
Parser
   |
Interpreter engine
   |
Execution
   |
Main program
```

## Project structure

- `src/main.py`: Entry point, contains the main interpreter loop
- `src/intrpr/`: Core interpreter, contains logic to execute commands
- `src/logger/`: Custom logging facility
- `src/parser/`: Parser, contains the parser (duh!)
- `src/utils/`: Project-wide "things"

### Core interpreter (`src/intrpr/`)

- `src/intrpr/cmd_reslvr.py`: Command resolver
- `src/intrpr/cfg_mgr.py`: Config manager, for loading and managing the
configuration file
- `src/intrpr/eng.py`: "Engine" of the interpreter, which houses the
interpreter object `Intrpr`

### Logging facility (`src/logger/`)

- `src/logger/eng.py`: Contains the logger class definition, and logger
"vessel" class definition

### Parser (`src/parser/`)

- `src/parser/ast_nodes.py`: Houses the AST node definitions
- `src/parser/eng.py`: Houses the main parser object
- `src/parser/internals.py`: Contains parser-specific attributes and data

### Utilities (`src/utils/`)

- `src/utils/consts.py`: Houses constants used by various parts of the project
- `src/utils/debug.py`: Contains debugging facilities
- `src/utils/err_codes.py`: Provides common errors codes that can be used by
command modules
- `src/utils/gen.py`: Provides the API for commands to interact with the
interpreter
