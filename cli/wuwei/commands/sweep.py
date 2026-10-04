"""Run an absolute-state sweep."""

from wuwei import obligations, watch


def register(subparsers):
    parser = subparsers.add_parser('sweep', help='Check day obligations')
    sweeps = parser.add_subparsers(dest='sweep', required=True)
    parser = sweeps.add_parser('obligations', help='Check open PR replies and visibility')
    parser.set_defaults(func=lambda args: obligations.sweep())
    parser = sweeps.add_parser('watch', help='Check watch health, obligations, activity and traces')
    parser.set_defaults(func=lambda args: watch.sweep())
