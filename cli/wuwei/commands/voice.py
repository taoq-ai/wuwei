"""Learn owner voice from read-only adapter history."""

from wuwei.voice import learn


def register(subparsers):
    voice = subparsers.add_parser('voice', help='owner voice profile')
    actions = voice.add_subparsers(dest='action', required=True)
    actions.add_parser('learn', help='propose owner voice examples').set_defaults(func=run)


def run(args):
    return learn()
