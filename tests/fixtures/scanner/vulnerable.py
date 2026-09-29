"""Deliberately unsafe fixture; never executed by tests."""


def agent(user_input):
    return eval(user_input)
