# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2022-2023, Markus Leiter <leiter@p2l2.com> | www.p2l2.com

import sys
from pathlib import Path
import subprocess
from subprocess import call, STDOUT
import os
from os.path import dirname
import logging
from glob import glob
from typing import Optional, List
import toml

logger = logging.getLogger('vunit_helpers')
logger.setLevel(logging.WARNING)


def enable_debug_logging():
    """ 
    Sets the logging level of the module internal logger to DEBUG.
    """
    logger.setLevel(logging.DEBUG)



def get_git_repo_root_path():
    """
    Returns the absolute path to the git repository root
    Returns None if the current directory is not within a git repository

    Args:
        path: 
    """
    if call(["git", "branch"], stderr=STDOUT, stdout=open(os.devnull, 'w')) != 0:
        return None
        logger.warning(f"This is not a git repository!")

    else:
        git_repo_dir = subprocess.Popen(
        ['git', 'rev-parse', '--show-toplevel'], stdout=subprocess.PIPE).communicate()[0].rstrip().decode("utf-8") 
        logger.debug(f"git repo path: {str(git_repo_dir)}")
    return Path(git_repo_dir)


def generate_rust_hdl_toml(VU, output_file, file_root_path):
    """
    Generate the toml file required by rust_hdl (vhdl_ls).

    Call this function after all sources were added to VUnit. 
    Precompiled libraries are cannot be handled by rust_hdl. 
    Therefor, precompiled UVVM libraries won't be covered in the toml file.

    Args:
        VU: A VUnit object file.
        output_file: A string containing the path to the output file.
        file_root_path: root path for relative filenames. The path is used to convert them to absolute paths
    """

    # TODO: check if precompiled libraries were added

    libs = VU.get_libraries()
    vhdl_ls = {"libraries": {}}
    for lib in libs:
        files = []
        for file in lib.get_source_files(allow_empty=True):
            if os.path.isabs(file.name):
                files.append(str(file.name))
            else:
                files.append(str(Path(file_root_path) / file.name))

        vhdl_ls["libraries"].update(
            {
                lib.name: {
                    "files": files
                }
            }
        )
    with open(output_file, "w") as f:
        toml.dump(vhdl_ls, f)
    logger.debug(f"rust_hdl configuration was written to {output_file}")


def add_uvvm_sources(VU,uvvm_path,libraries=None):
    """
    UVVM https://github.com/UVVM/UVVM is a free and Open Source Methodology and Library which can be used in combination with VUnit.
    Use add_uvvm to add the UVVM sources from a given path. 
    Since UVVM is not included in VUnit, it must be cloned separately. 

    Usage examples: 
    VU.add_uvvm(uvvm_path="../UVVM") # To add all UVVM libraries

    To decrease the compile duration, you can specify the libraries needed for simulation. 
    The following example would compile  uvvm_util, uvvm_vvc_framework and bitvis_vip_clock_generator only:
    VU.add_uvvm(uvvm_path="../UVVM", libraries=['uvvm_util', 'uvvm_vvc_framework','bitvis_vip_clock_generator'])

    UVVM provides txt files with compile information. There is one txt file that lists all libraries of UVVM called component_list.txt.
    Then, there is one file per component that lists all files of the library in compile order. This file is called compile_order.txt. 

    :param uvvm_path: absolute or relative path pointing to the UVVM source directory e.g. '../UVVM'
    :param libraries: List of UVVM libraries that are used. If libraries is None, all UVVM libraries are added to VUnit
    """

    # load the list of available UVVM components
    component_list_file = Path(uvvm_path) / "script" / "component_list.txt"
    if not Path(component_list_file).exists():
        raise ValueError(f"Found no file named '{component_list_file!s}'. Probably, the UVVM path is incorrect (uvvm_path={uvvm_path}).")

    uvvm_components = []
    with open(component_list_file) as f:
        uvvm_components = [s.strip() for s in f.readlines()] # read all components from component_list.txt
        uvvm_components = [s for s in uvvm_components if (not s.startswith("#")) and s] # remove comments and empty lines

    if libraries != None:
        # check if all given libraries are available in UVVM
        if not all(libname in uvvm_components for libname in libraries):
            raise ValueError(f"some requested libraries are not available in UVVM. Requested: {libraries}, Available UVVM Components: {uvvm_components}")
        uvvm_components = libraries 

    # add source files of the components
    for component in uvvm_components:
        lib = VU.add_library(component)

        script_dir = Path(uvvm_path) / component / "script"
        source_files = []
        with open(script_dir / "compile_order.txt") as f:
            source_files = [s.strip() for s in f.readlines()] # read all lines including comments
            source_files = [s for s in source_files if (not s.startswith("#")) and s] # remove comments and empty lines
            #add the full path to the list of source files
            source_files = [os.path.abspath(script_dir / Path(s)) for s in source_files]

        # add the files
        lib.add_source_files(source_files)


def add_precompiled_uvvm_libraries(VU, used_libraries, UVVM_root_path):
    """ 
    Add the passed UVVM libraries to VUnit. 

    To compile UVVM using modelsim, use the script compile_all.do located at UVVM/script
    To compile UVVM using ghdl, use the script located at GHDL/src/scripts/vendors/compile-uvvm.ps1. 
    Do not forget to setup the set the InstallationDirectory and the DestinationDirectory in config.ps1!

    Args:
        VU: A VUnit object file.
        used_libraries: A list of uvvm libraries. E.g. ['uvvm_util','uvvm_vvc_framework','bitvis_vip_scoreboard','bitvis_vip_clock_generator']
        UVVM_root_path: root path pointing to the UVVM directory. E.g. get_git_repo_root_path() / "verification" / "uvvm"
    """
    logger.debug(f"Active simulator={VU.get_simulator_name()}")

    if VU.get_simulator_name() == "modelsim":
        for libname in used_libraries:
            location = UVVM_root_path / libname / "sim" / libname
            VU.add_external_library(libname, location)
            logger.debug(f"adding library {libname} from {str(location)}")
    elif VU.get_simulator_name() == "ghdl":
        for libname in used_libraries:
            location = UVVM_root_path / libname / "v08"
            VU.add_external_library(libname, location)
            logger.debug(f"adding library {libname} from {str(location)}")
    else:
        logger.error(
            f"Adding precompiled UVVM libraries for simulator {VU.get_simulator_name()} is not supported. You can use add_uvvm_sources() instead")


def set_ghdl_flags_for_UVVM(VU):
    """ 
    Set all necessary flags to compile UVVM with GHDL

    Args:
        VU: A VUnit object file.

    """
    VU.add_compile_option("ghdl.a_flags", value=[
        "-Wno-hide",
        "-fexplicit",
        "-Wbinding",
        "-Wno-shared",
        "--ieee=synopsys",
        "--no-vital-checks",
        "--std=08",
        "-frelaxed",
        "-frelaxed-rules",
        # "-v"
    ])

    VU.set_sim_option("ghdl.elab_flags", value=[
        "-Wno-hide",
        "-fexplicit",
        "-Wbinding",
        "-Wno-shared",
        "--ieee=synopsys",
        "--no-vital-checks",
        "--std=08",
        "-frelaxed",
        "-frelaxed-rules"
    ])

    VU.set_sim_option("ghdl.elab_e", overwrite=True, value=True)
    logger.debug(f"GHDL flags for UVVM were set")


class File_pattern:
    def __init__(self, pattern, when_simulator_is=None, when_simulator_is_not=None):
        self.pattern = str(pattern)

        if isinstance(when_simulator_is, str):
            self.include_simulators = [when_simulator_is]
        else:
            self.include_simulators = when_simulator_is

        if isinstance(when_simulator_is_not, str):
            self.exclude_simulators = [when_simulator_is_not]
        else:
            self.exclude_simulators = when_simulator_is_not


def advanced_add_source_files(VU, lib, include_patterns, 
                              exclude_patterns=None,
                              preprocessors=None,
                              include_dirs=None,
                              defines=None,
                              allow_empty=False,
                              vhdl_standard: Optional[str] = None,
                              no_parse=False,
                              file_type=None,
                              ):
    """ 
    Advanced method to include files in VUnit. This functions allows to specify include and exclude patterns for specific simulators. 
    The function evaluates all include patterns first and removes all excluded files afterwards. 

    Args:
        VU: A VUnit object file.
        lib: the lib where the files will be added
        include_patterns: A list of File_patterns that shall be added to the lib
        exclude_patterns: A list of File_patterns that shall be excluded from the include_patterns
        All other Arguments are derived from VUnit.library.add_source_files() and directly passed through

    """

    include_files:List[str] = []
    for file_pattern in include_patterns:
        if ((file_pattern.include_simulators == None) or (VU.get_simulator_name() in file_pattern.include_simulators)) and ((file_pattern.exclude_simulators == None) or not (VU.get_simulator_name() in file_pattern.include_simulators)):
            files = glob(file_pattern.pattern, recursive=True)
            if not files:
                logger.warning(
                    f"Include file pattern {file_pattern.pattern} did not match any file!")
            else:
                include_files += files
        else:
            logger.debug(
                f"include pattern {file_pattern.pattern} was not processed due to the used simulator ({VU.get_simulator_name()})")

    exclude_files:List[str] = []
    if exclude_patterns is not None:
        for file_pattern in exclude_patterns:
            if ((file_pattern.include_simulators == None) or (VU.get_simulator_name() in file_pattern.include_simulators)) and ((file_pattern.exclude_simulators == None) or not (VU.get_simulator_name() in file_pattern.include_simulators)):
                files = glob(file_pattern.pattern, recursive=True)
                if not files:
                    logger.warning(
                        f"Exclude file pattern {file_pattern.pattern} did not match any file!")
                else:
                    exclude_files += files
            else:
                logger.debug(
                    f"exclude pattern {file_pattern.pattern} was not processed due to the used simulator ({VU.get_simulator_name()})")

    file_names = [x for x in include_files if x not in exclude_files]


    for incl in include_files:
        logger.debug(f"including {incl}")
    for excl in exclude_files:
        logger.debug(f"excluding {excl}")
    for remaining in file_names:
        logger.debug(f"remaining {remaining}")

    lib.add_source_files(file_names,
                         preprocessors=preprocessors,
                         include_dirs=include_dirs,
                         defines=defines,
                         allow_empty=allow_empty,
                         vhdl_standard=vhdl_standard,
                         no_parse=no_parse,
                         file_type=file_type)
