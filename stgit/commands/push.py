# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

from stgit.argparse import keep_option, merged_option, opt, patch_range
from stgit.commands.common import CmdException, DirectoryHasRepository, parse_patches
from stgit.lib import transaction

__copyright__ = """
Copyright (C) 2005, Catalin Marinas <catalin.marinas@gmail.com>

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License version 2 as
published by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, see http://www.gnu.org/licenses/.
"""

help = 'Push one or more patches onto the stack'
kind = 'stack'
usage = ['[options] [--] [<patch1>] [<patch2>] [<patch3>..<patch4>]']
description = """
Push one or more patches (defaulting to the first unapplied one) onto
the stack. The 'push' operation allows patch reordering by commuting
them with the three-way merge algorithm. If there are conflicts while
pushing a patch, those conflicts are written to the work tree, and the
command halts. Conflicts raised during the push operation have to be
fixed and the 'git add --update' command run (alternatively, you may
undo the conflicting push with 'stg undo').

The command also notifies when the patch becomes empty (fully merged
upstream) or is modified (three-way merged) by the 'push' operation."""

args = [patch_range('unapplied_patches')]
options = (
    [
        opt(
            '-a', '--all', action='store_true', short='Push all the unapplied patches',
        ),
        opt(
            '-n',
            '--number',
            type='int',
            short='Push the specified number of patches',
            long='''
        Push the specified number of patches.

        With a negative number, push all but that many patches.''',
        ),
        opt(
            '--reverse', action='store_true', short='Push the patches in reverse order',
        ),
        opt(
            '--set-tree',
            action='store_true',
            short='Push the patch with the original tree',
            long="""
        Push the patches, but don't perform a merge. Instead, the
        resulting tree will be identical to the tree that the patch
        previously created.

        This can be useful when splitting a patch by first popping the
        patch and creating a new patch with some of the
        changes. Pushing the original patch with '--set-tree' will
        avoid conflicts and only the remaining changes will be in the
        patch.""",
        ),
    ]
    + keep_option()
    + merged_option()
)

directory = DirectoryHasRepository()


def func(parser, options, args):
    """Pushes the given patches or the first unapplied onto the stack."""
    stack = directory.repository.current_stack
    iw = stack.repository.default_iw
    clean_iw = (not options.keep and iw) or None
    trans = transaction.StackTransaction(stack, 'push', check_clean_iw=clean_iw)

    if options.number == 0:
        # explicitly allow this without any warning/error message
        return

    if not trans.unapplied:
        raise CmdException('No patches to push')

    if options.all:
        patches = list(trans.unapplied)
    elif options.number is not None:
        patches = trans.unapplied[: options.number]
    elif not args:
        patches = [trans.unapplied[0]]
    else:
        try:
            patches = parse_patches(args, trans.unapplied)
        except CmdException as e:
            try:
                patches = parse_patches(args, trans.applied)
            except CmdException:
                raise e
            else:
                raise CmdException(
                    'Patch%s already applied: %s'
                    % ('es' if len(patches) > 1 else '', ', '.join(patches))
                )

    assert patches

    if options.reverse:
        patches.reverse()

    if options.set_tree:
        for pn in patches:
            trans.push_tree(pn)
    else:
        try:
            if options.merged:
                merged = set(trans.check_merged(patches))
            else:
                merged = set()
            for pn in patches:
                trans.push_patch(
                    pn, iw, allow_interactive=True, already_merged=pn in merged
                )
        except transaction.TransactionHalted:
            pass
    return trans.run(iw)
