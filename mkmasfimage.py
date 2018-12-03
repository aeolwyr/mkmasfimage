#!/usr/bin/env python3
# Kaan Karaagacli
""" Create a MASF (Metadata and Small Files) image from a folder.
The small files are preserved according to the given rules,
and the metadata of the rest of the files are preserved.

Optionally the filesizes of the large files can be stored,
but this slows down the image creation process considerably.

The small files are copied to a temporary folder (which usually
resides in RAM), therefore make sure you have enough space there. """

import argparse
import os
import pathlib
import shutil
import subprocess
import tempfile


def parse_filesize(filesize):
    """ Parse a human readable filesize string into a integer.
    Only the suffixes 'k' and 'M' are supported. """
    try:
        if filesize.endswith('k'):
            return int(filesize[:-1]) * 1024
        if filesize.endswith('M'):
            return int(filesize[:-1]) * 1048576
        return int(filesize)
    except ValueError as error:
        # include the original exception
        raise ValueError('Invalid size: {}'.format(filesize)) from error

def make_masf_image(source_folder, destination_file,
                    exclusion_rules, global_size_limit, store_filesizes=False):
    """ Create a MASF image of a given directory.

    Keyword arguments:
    source_folder -- folder to create its image, its root is not included
    destination_file -- image file to be created
    exclusion_rules -- a dictionary with extensions (i.e. ".txt")
                       as its keys, and the maximum permitted size
                       as its values
    store_filesizes -- whether to store the filesize information in
                       the image or not, significantly slows down the
                       process when enabled """

    def copy_function(src, dst, *, follow_symlinks=True):
        size = os.path.getsize(src)
        if size < global_size_limit:
            # copy as normal
            return shutil.copy2(src, dst, follow_symlinks=follow_symlinks)
        for extension, size_limit in exclusion_rules.items():
            # extension is in exclusion rules, keep if the filesize
            # is not very large
            if src.endswith(extension) and size < size_limit:
                # copy as normal
                return shutil.copy2(src, dst, follow_symlinks=follow_symlinks)
        # the file was not copied normally, create an empty file
        pathlib.Path(dst).touch()
        if store_filesizes:
            # use the truncate function to set the filesizes if requested
            os.truncate(dst, size)
        # copy the attributes only
        return shutil.copystat(src, dst, follow_symlinks=follow_symlinks)

    # prepare a temp folder to create its image
    with tempfile.TemporaryDirectory() as tmpdirname:
        # copytree requires a non-existing directory
        tmpdirname = os.path.join(tmpdirname, 'dst')

        try:
            shutil.copytree(source_folder, tmpdirname, symlinks=True,
                            copy_function=copy_function)
        except shutil.Error as errors:
            for error in errors.args[0]:
                print(error[2])

        # create the image
        subprocess.run(['mksquashfs', tmpdirname, destination_file])

def main():
    """ Entry point for this script, in case it is invoked on the command line. """
    parser = argparse.ArgumentParser(
        description='Create a MASF (Metadata and Small Files) image.',
        epilog='For the size values, units k and M are supported')

    parser.add_argument('-s', '--store-filesizes', action='store_true',
                        help='''include the sizes of the files, slows down
                        the image creation process considerably''')

    parser.add_argument('-g', '--global-limit', default='0', metavar='SIZE',
                        help='file size limit for the non-excluded files')

    parser.add_argument('rules', metavar='rule',
                        help='''exclusion rules, in the format of EXT=SIZE
                        where the EXT the extension of the file (e.g. ".txt")
                        and the SIZE is the maximum size allowed for these
                        type of files''', nargs='*')

    parser.add_argument('source', help='source folder')
    parser.add_argument('destination', help='image file to create')

    args = parser.parse_args()

    # convert the ".EXT=10" style input to ".EXT":10 (dictionary item)
    rules_split = [x.split('=', 1) for x in args.rules]
    rules_dict = {x[0]: parse_filesize(x[1]) for x in rules_split}

    global_limit = parse_filesize(args.global_limit)

    make_masf_image(source_folder=args.source,
                    destination_file=args.destination,
                    exclusion_rules=rules_dict,
                    global_size_limit=global_limit,
                    store_filesizes=args.store_filesizes)

if __name__ == '__main__':
    main()
