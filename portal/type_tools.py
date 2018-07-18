from flask import abort


def check_int(i):
    try:
        return int(i)
    except ValueError, e:
        abort(400, "invalid input '{}' - must be an integer".format(i))
