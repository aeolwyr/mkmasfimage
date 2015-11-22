#!/usr/bin/env python3
# Kaan Karaagacli
""" Create a MASF (Metadata and Small Files) image from a folder.
The small files are preserved according to the given rules,
and the metadata of the rest of the files are preserved.

Optionally the filesizes of the large files can be stored,
but this slows down the image creation process considerably.

The small files are copied to a temporary folder (which usually
resides in RAM), therefore make sure you have enough space there. """

import argparse, os, subprocess, tempfile

def get_all_files(folder):
    """ Iterate through all the files in a folder, including subfolders. """
    for dirpath, dirnames, filenames in os.walk(folder):
        for filename in filenames:
            yield os.path.join(dirpath, filename)

def parse_filesize(filesize):
    """ Parse a human readable filesize string into a integer.
    Only the suffixes 'k' and 'M' are supported. """
    try:
        if filesize.endswith('k'):
            return int(filesize[:-1]) * 1024
        elif filesize.endswith('M'):
            return int(filesize[:-1]) * 1048576
        else:
            return int(filesize)
    except ValueError as e:
        # include the original exception
        raise ValueError('Invalid size: {}'.format(filesize)) from e

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
    original_dir = os.getcwd()
    try:
        # navigate to the source directory
        os.chdir(source_folder)
        make_masf_image_of_current_folder(destination_file,
                exclusion_rules, global_size_limit, store_filesizes)
    finally:
        # return to the original directory when finished
        os.chdir(original_dir)

def make_masf_image_of_current_folder(destination_file,
        exclusion_rules, global_size_limit, store_filesizes=False):
    """ Create a MASF image of the current working directory. """
    files_to_keep = set()
    files_to_empty = set()

    # determine which files to keep
    for filename in get_all_files('.'):
        filesize = os.stat(filename).st_size
        for extension, size_limit in exclusion_rules.items():
            # extension is in exclusion rules, keep if the filesize
            # is not very large
            if filename.endswith(extension) and filesize < size_limit:
                files_to_keep.add(filename)
                break
        else:
            # this else block is executed if the loop above never breaks,
            # i.e. the file is not excluded
            if filesize < global_size_limit:
                files_to_keep.add(filename)
            else:
                files_to_empty.add(filename)

    # prepare a temp folder to create its image
    with tempfile.TemporaryDirectory() as tmpdirname:
        if files_to_keep:
            # copy as normal
            full_copy = ['cp', '--archive', '--parents']
            full_copy.extend(files_to_keep)
            full_copy.append(tmpdirname)
            subprocess.run(full_copy)

        if files_to_empty:
            # copy the attributes only
            create_empty = ['cp', '--archive', '--attributes-only', '--parents']
            create_empty.extend(files_to_empty)
            create_empty.append(tmpdirname)
            subprocess.run(create_empty)

            if store_filesizes:
                # use the truncate utility to set the filesizes if requested
                for filename in files_to_empty:
                    subprocess.run([
                            'truncate',
                            '--reference=' + filename,
                            os.path.join(tmpdirname, filename)])

        # create the image
        subprocess.run(['mksquashfs', tmpdirname, destination_file])

if __name__ == '__main__':
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
