"""No speech output."""

from wuwei.registry import Result


def speak(text, rate, out, root=None):
    return Result(0, {'performed': False, 'reason': 'tts: none'})
