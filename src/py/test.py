from src.utils import err_codes as uerr
from src.utils import gen as ugen

CMD_NM = __name__.split(".")[-1]

HELP = ugen.HelpObj(
    usage=CMD_NM,
    summary="Just a test command",
    details=(
        "ARGUMENTS",
        ("none", ""),
        "OPTIONS",
        ("none", ""),
        "FLAGS",
        ("none", "")
    )
)

CMD_SPEC = ugen.CmdSpec(
    min_args=0,
    max_args=0,
    opts=(),
    flags=()
)


def high_mem(data: ugen.CmdData) -> None:
    ugen.write(data.stdin)
    full = 10 ** 8
    segment = full // 5
    for j, i in enumerate(range(segment, full, segment)):
        ugen.write(str(j) * i)
        " " * 10 ** 10


def run(data: ugen.CmdData) -> int:
    # data.env_vars["foo"] = "bar"
    # data.env_vars["haha"] = "hehe"
    # ugen.write(str(data.env_vars.cnt))
    # print(data.env_vars)
    # ugen.write(data.env_vars["foo"] + "\n")
    # ugen.write(data.stdin)
    ugen.write("""The os._exit() function can be used if it is absolutely positively necessary to exit immediately (for example, in the child process after a call to os.fork()).
    code
        The exit status or error message that is passed to the constructor. (Defaults to None.)
exception TypeError
    Raised when an operation or function is applied to an object of inappropriate type. The associated value is a string giving details about the type mismatch.
    This exception may be raised by user code to indicate that an attempted operation on an object is not supported, and is not meant to be. If an object is meant to support a given operation but has not yet provided an implementation, NotImplementedError is the proper exception to raise.
    Passing arguments of the wrong type (e.g. passing a list when an int is expected) should result in a TypeError, but passing arguments with the wrong value (e.g. a number outside expected boundaries) should result in a ValueError.
exception UnboundLocalError
    Raised when a reference is made to a local variable in a function or method, but no value has been bound to that variable. This is a subclass of NameError.
exception UnicodeError
    Raised when a Unicode-related encoding or decoding error occurs. It is a subclass of ValueError.
    UnicodeError has attributes that describe the encoding or decoding error. For example, err.object[err.start:err.end] gives the particular invalid input that the codec failed on.
    encoding
        The name of the encoding that raised the error.
    reason
        A string describing the specific codec error.
    object
        The object the codec was attempting to encode or decode.
    start
        The first index of invalid data in object.
        This value should not be negative as it is interpreted as an absolute offset but this constraint is not enforced at runtime.
    end
        The index after the last invalid data in object.
        This value should not be negative as it is interpreted as an absolute offset but this constraint is not enforced at runtime.
exception UnicodeEncodeError
    Raised when a Unicode-related error occurs during encoding. It is a subclass of UnicodeError.
exception UnicodeDecodeError
    Raised when a Unicode-related error occurs during decoding. It is a subclass of UnicodeError.
exception UnicodeTranslateError
    Raised when a Unicode-related error occurs during translating. It is a subclass of UnicodeError.
exception ValueError
    Raised when an operation or function receives an argument that has the right type but an inappropriate value, and the situation is not described by a more precise exception such as IndexError.
exception ZeroDivisionError
    Raised when the second argument of a division or modulo operation is zero. The associated value is a string indicating the type of the operands and the operation.
The following exceptions are kept for compatibility with previous versions; starting from Python 3.3, they are aliases of OSError.
exception EnvironmentError
exception IOError
exception WindowsError
    Only available on Windows.
OS exceptions
The following exceptions are subclasses of OSError, they get raised depending on the system error code.
exception BlockingIOError
    Raised when an operation would block on an object (e.g. socket) set for non-blocking operation. Corresponds to errno EAGAIN, EALREADY, EWOULDBLOCK and EINPROGRESS.
    In addition to those of OSError, BlockingIOError can have one more attribute:
    characters_written
        An integer containing the number of bytes written to the stream before it blocked. This attribute is available when using the buffered I/O classes from the io module.
exception ChildProcessError
    Raised when an operation on a child process failed
""")
    return uerr.ERR_ALL_GOOD


# def run(data: ugen.CmdData) -> int:
#     ugen.write(data.stdin)
#     data.env_vars["sneha"] = "hello"
#     data.intrpr_vars["thiru"] = "world"
#     return uerr.ERR_ALL_GOOD
