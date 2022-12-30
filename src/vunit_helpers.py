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


def generate_rust_hdl_toml(VU, output_file):
    """
    Generate the toml file required by rust_hdl (vhdl_ls).

    Call this function after all sources were added to VUnit. 
    Precompiled libraries are cannot be handled by rust_hdl. 
    Therefor, precompiled UVVM libraries won't be covered in the toml file.

    Args:
        VU: A VUnit object file.
        output_file: A string containing the path to the output file.
    """

    # TODO: check if precompiled libraries were added

    libs = VU.get_libraries()
    vhdl_ls = {"libraries": {}}
    for lib in libs:
        vhdl_ls["libraries"].update(
            {
                lib.name: {
                    "files": [f"verification/{file.name}" for file in lib.get_source_files(allow_empty=True)]
                }
            }
        )
    with open(output_file, "w") as f:
        toml.dump(vhdl_ls, f)
    logger.debug(f"rust_hdl configuration was written to {output_file}")


def add_uvvm_sources(VU, used_libraries, UVVM_root_path):
    """ 
    Add the passed UVVM libraries as source files to VUnit. 

    VUnit will handle analyze the compile order. This way, no precompilation of UVVM is needed.
    Args:
        VU: A VUnit object file.
        used_libraries: A list of uvvm libraries. E.g. ['uvvm_util','uvvm_vvc_framework','bitvis_vip_scoreboard','bitvis_vip_clock_generator']
        UVVM_root_path: root path pointing to the UVVM directory. E.g. get_git_repo_root_path() / "verification" / "uvvm"
    """

    for libname in used_libraries:
        LIBuvvm = VU.add_library(libname)
        LIBuvvm.add_source_files(UVVM_root_path / libname / "src" / "*.vhd")
        if libname != "uvvm_vvc_framework" and libname != "uvvm_util" and libname != "bitvis_vip_scoreboard":
            LIBuvvm.add_source_files(
                UVVM_root_path / "uvvm_vvc_framework" / "src_target_dependent" / "*.vhd")


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


def advanced_add_source_files(VU, lib, include_patterns: list[File_pattern], exclude_patterns: list[File_pattern] = None,
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
