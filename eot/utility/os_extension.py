import glob
import os
import shutil
from functools import reduce
import re


def delete_files_in_dir(
    idp, ext=None, target_str_or_list=None, sort_result=True, recursive=False
):

    """ext can be a list of extensions or a single extension
    (e.g. ['.jpg', '.png'] or '.jpg')
    """

    fps = get_file_paths_in_dir(
        idp,
        ext=ext,
        target_str_or_list_in_fn=target_str_or_list,
        sort_result=sort_result,
        recursive=recursive,
    )

    for fp in fps:
        assert os.path.isfile(fp)
        os.remove(fp)


def glob_re(pattern, strings):
    # https://stackoverflow.com/questions/13031989/regular-expression-usage-in-glob-glob
    """Alternative to glob using regular expressions.

    Aims to overcome limitations of glob (e.g. no optional strings supported).
    Usage: filenames = glob_re(r'.*(abc|123|a1b).*', os.listdir())
    """
    return filter(re.compile(pattern).match, strings)


def natural_key(some_string):
    """See http://www.codinghorror.com/blog/archives/001018.html"""
    return [
        int(s) if s.isdigit() else s for s in re.split(r"(\d+)", some_string)
    ]


def check_ext(ext):
    # Check if extension is valid (contains a leading dot)
    if isinstance(ext, list):
        for ele in ext:
            assert ele[0] == ".", "Invalid extension, leading dot missing"
    else:
        assert ext[0] == ".", "Invalid extension, leading dot missing"


def get_regex_fps_in_dp(idp, search_regex, ignore_regex):

    glob_search_expr = os.path.join(idp, search_regex)
    search_ifps = glob.glob(glob_search_expr, recursive=True)

    glob_ignore_expr = os.path.join(idp, ignore_regex)
    ignore_ifps = glob.glob(glob_ignore_expr, recursive=True)
    # Use a set to accelerate existence check: https://wiki.python.org/moin/TimeComplexity
    ignore_ifps_set = set(ignore_ifps)
    ifps = [ifp for ifp in search_ifps if ifp not in ignore_ifps_set]
    err_msg = (
        f"Found no images using {{{glob_search_expr} / {glob_ignore_expr}}}"
    )
    assert len(ifps), err_msg

    return ifps


def get_file_paths_in_dir(
    idp,
    ext=None,
    target_str_or_list_in_fn=None,
    target_str_or_list_in_fp=None,
    ignore_str_or_list_in_fn=None,
    ignore_str_or_list_in_fp=None,
    base_name_only=False,
    without_ext=False,
    sort_result=True,
    natural_sorting=False,
    recursive=False,
):

    """ext can be a list of extensions or a single extension
    (e.g. ['.jpg', '.png'] or '.jpg')
    """

    if recursive:
        ifp_s = []
        for root, dirs, files in os.walk(idp):
            ifp_s += [os.path.join(root, ele) for ele in files]
    else:
        ifp_s = [
            os.path.join(idp, ele)
            for ele in os.listdir(idp)
            if os.path.isfile(os.path.join(idp, ele))
        ]

    if ext is not None:
        if isinstance(ext, list):
            ext = [ele.lower() for ele in ext]
            check_ext(ext)
            ifp_s = [
                ifp for ifp in ifp_s if os.path.splitext(ifp)[1].lower() in ext
            ]
        else:
            ext = ext.lower()
            check_ext(ext)
            ifp_s = [
                ifp for ifp in ifp_s if os.path.splitext(ifp)[1].lower() == ext
            ]

    if target_str_or_list_in_fn is not None:
        if type(target_str_or_list_in_fn) == str:
            target_str_or_list_in_fn = [target_str_or_list_in_fn]
        for target_str in target_str_or_list_in_fn:
            ifp_s = [
                ifp for ifp in ifp_s if target_str in os.path.basename(ifp)
            ]

    if target_str_or_list_in_fp is not None:
        if type(target_str_or_list_in_fp) == str:
            target_str_or_list_in_fp = [target_str_or_list_in_fp]
        for target_str in target_str_or_list_in_fp:
            ifp_s = [ifp for ifp in ifp_s if target_str in ifp]

    if ignore_str_or_list_in_fn is not None:
        if type(ignore_str_or_list_in_fn) == str:
            ignore_str_or_list_in_fn = [ignore_str_or_list_in_fn]
        for ignore_str in ignore_str_or_list_in_fn:
            ifp_s = [
                ifp for ifp in ifp_s if ignore_str not in os.path.basename(ifp)
            ]

    if ignore_str_or_list_in_fp is not None:
        if type(ignore_str_or_list_in_fp) == str:
            ignore_str_or_list_in_fp = [ignore_str_or_list_in_fp]
        for ignore_str in ignore_str_or_list_in_fp:
            ifp_s = [ifp for ifp in ifp_s if ignore_str not in ifp]

    if base_name_only:
        ifp_s = [os.path.basename(ifp) for ifp in ifp_s]

    if without_ext:
        ifp_s = [os.path.splitext(ifp)[0] for ifp in ifp_s]

    if sort_result:
        if natural_sorting:
            ifp_s = sorted(ifp_s, key=natural_key)
        else:
            ifp_s = sorted(ifp_s)

    return ifp_s


def get_image_file_paths_in_dir(
    idp,
    base_name_only=False,
    without_ext=False,
    sort_result=True,
    recursive=True,
    target_str_or_list=None,
):
    return get_file_paths_in_dir(
        idp,
        ext=[".jpg", ".png"],
        target_str_or_list_in_fn=target_str_or_list,
        base_name_only=base_name_only,
        without_ext=without_ext,
        sort_result=sort_result,
        recursive=recursive,
    )


def get_corresponding_files_in_directories(
    idp_1,
    idp_2,
    ext_1=None,
    suffix_2="",
    get_correspondence_callback=None,
    sort_result=True,
):

    if get_correspondence_callback is None:

        def get_correspondence_callback(fn_1):
            return fn_1 + suffix_2

    potential_fn_1_list = get_file_paths_in_dir(
        idp_1,
        ext=ext_1,
        base_name_only=True,
        sort_result=sort_result,
    )
    fp_1_list = []
    fp_2_list = []
    for fn_1 in potential_fn_1_list:
        fp_2 = os.path.join(idp_2, get_correspondence_callback(fn_1))
        # print(fp_2)
        if os.path.isfile(fp_2):
            fp_1_list.append(os.path.join(idp_1, fn_1))
            fp_2_list.append(fp_2)
    return fp_1_list, fp_2_list


def delete_subdirs(idp, filter_dp, recursive=False, dry_run=True):

    sub_dirs = get_subdirs(idp, recursive=recursive)
    sub_dirs_to_delete = []
    for sub_dir in sub_dirs:
        if sub_dir.endswith(filter_dp):
            sub_dirs_to_delete.append(sub_dir)

    if dry_run:
        print("Dry run! (Files will not be deleted)")
    else:
        for dir in sub_dirs_to_delete:
            shutil.rmtree(dir, ignore_errors=True)
    print("sub_dirs_to_delete:")
    print(sub_dirs_to_delete)


def get_subdirs(idp, base_name_only=False, recursive=False):

    if recursive:
        sub_dps = []
        if base_name_only:
            for root, dirs, files in os.walk(idp):
                sub_dps += [name for name in dirs]
        else:
            for root, dirs, files in os.walk(idp):
                sub_dps += [os.path.join(root, sub_dn) for sub_dn in dirs]
    else:
        sub_dns = [
            name
            for name in os.listdir(idp)
            if os.path.isdir(os.path.join(idp, name))
        ]
        if base_name_only:
            sub_dps = sub_dns
        else:
            sub_dps = [os.path.join(idp, sub_dn) for sub_dn in sub_dns]

    return sub_dps


def get_stem(ifp, base_name_only=True):
    if base_name_only:
        ifp = os.path.basename(ifp)
    return os.path.splitext(ifp)[0]


def get_basename(ifp):
    return os.path.basename(ifp)


def mkdir_safely(odp):
    if not os.path.isdir(odp):
        os.mkdir(odp)


def makedirs_safely(odp):
    if not os.path.isdir(odp):
        os.makedirs(odp)


def ensure_trailing_slash(some_path):
    return os.path.join(some_path, "")


def get_first_valid_path(list_of_paths):
    first_valid_path = None
    for path in list_of_paths:
        if first_valid_path is None and (
            os.path.isdir(path) or os.path.isfile(path)
        ):
            first_valid_path = path
    return first_valid_path


def get_folders_matching_scheme(path_to_image_folders, pattern):
    target_folder_paths = []
    for root, dirs, files in os.walk(path_to_image_folders):

        match_result = pattern.match(os.path.basename(root))

        if match_result:  # basename matched the pattern
            target_folder_paths.append(root)

        # if os.path.basename(root) == target_folder_name_scheme:
        #     print 'Found Target Folder: ' + str(root)
        #     target_folder_paths.append(root)
    return target_folder_paths


def get_most_specific_parent_dir(possible_parent_dirs, possible_sub_dir):

    # print 'possible_sub_dir'
    # print possible_sub_dir

    current_parent_dir = ""

    for possible_parent_dir in possible_parent_dirs:

        # print 'possible_parent_dir'
        # print possible_parent_dir

        if is_subdir(possible_parent_dir, possible_sub_dir):

            # print 'is sub dir'

            if current_parent_dir == "":
                current_parent_dir = possible_parent_dir
            else:  # there is another parent dir already found

                result = is_subdir(current_parent_dir, possible_parent_dir)
                if result:
                    print("WARNING: FOUND A MORE SPECIFIC PARENT DIR")
                    print("current_parent_dir: " + current_parent_dir)
                    print("possible_parent_dir" + possible_parent_dir)
                    current_parent_dir = possible_parent_dir

    return current_parent_dir


def is_subdir(possible_parent_dir, possible_sub_dir):
    possible_parent_dir = os.path.realpath(possible_parent_dir)
    possible_sub_dir = os.path.realpath(possible_sub_dir)

    return possible_sub_dir.startswith(possible_parent_dir + os.sep)


def exist_files(file_list):
    return all(map(os.path.isfile, file_list))


def are_dirs_equal(idp_1, idp_2):
    fp_1_list = get_file_paths_in_dir(idp_1, base_name_only=True)
    fp_2_list = get_file_paths_in_dir(idp_2, base_name_only=True)

    return fp_1_list == fp_2_list
