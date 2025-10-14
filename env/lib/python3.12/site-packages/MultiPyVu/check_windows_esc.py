from sys import platform


if platform == 'win32':
    import msvcrt as _msvcrt    # Used to help detect the esc-key


def _check_windows_esc() -> None:
    """
    Windows looks for the ESC key to quit.

    Raises:
    -------
    Throws a KeyboardInterrupt if the esc key is hit.
    """
    if platform == 'win32':
        if (_msvcrt.kbhit()
                and _msvcrt.getch().decode() == chr(27)):
            raise KeyboardInterrupt
