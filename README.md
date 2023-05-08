# VUnit-helpers

This package contains project independent tools and helpers to simplify VUnit run scripts.
Using this, the run script gets shorter, more readable and easier to maintain. 

# Installing VUnit_helpers
You can install this package from source or via PyPi

## Installing via PyPi

    python -m pip install vunit_helpers

## Installing from source:
1. Clone or download the repository
2. navigate to the directory and run ```python -m pip install .```

Optionally add the ```-e``` flag to install the package in the editable mode.

# Usage Examples

## Get the root path of a git repository
Working with relative paths in VUnit is dangerouse, since it depends on the working directory of python during execution. Instead, you can use your git repository as the root reference of all paths.
``` Python
import vunit_helpers
git_repo_path = vunit_helpers.get_git_repo_root_path()
```

## Add UVVM to VUnit

Use vunit_helpers.add_uvvm_sources() to add all UVVM source files to VUnit. VUnit will compile UVVM in the correct order.  

``` Python
from vunit import VUnit
import vunit_helpers

VU = VUnit.from_argv()
# add all UVVM components
vunit_helpers.add_uvvm_sources(VU, git_repo_path / "UVVM")

# add some specific UVVM components only
vunit_helpers.add_uvvm_sources(VU, git_repo_path / "UVVM", ["uvvm_util", "uvvm_vvc_framework", "bitvis_vip_scoreboard", "bitvis_vip_uart"])
```

If you have precompiled UVVM using its compile_all.do TCL script, you can use vunit_helpers.add_precompiled_uvvm_libraries():
``` Python
VU = VUnit.from_argv()
vunit_helpers.add_precompiled_uvvm_libraries(VU,["uvvm_util", "uvvm_vvc_framework", "bitvis_vip_scoreboard", "bitvis_vip_uart"],"path/to/UVVM")
```

## Advanced add Source Files
Vunit helpers allows including and excluding wildcard patterns. That way, it's easier to exclude specific files from VUnit. 
``` Python
from vunit import VUnit
import vunit_helpers
from vunit_helpers import File_pattern

VU = VUnit.from_argv()
lib = VU.add_library("lib") 

include_patterns=[
    File_pattern(git_repo_path  / "verification"/ "*" / "hdl" / "*.vhd"),
    File_pattern(git_repo_path  / "units" / "unit*" / "tb" / "*.vhd"),
]

# The files that match the exclude patterns won't be added to the lib (these files are excluded from the include_patterns)
exclude_patterns=[
    # the SPI testbench uses external_names, that are not supported in GHDL yet
    File_pattern(git_repo_path  / "units" / "unit*" / "tb" / "tb_Formal.vhd", when_simulator_is_not="ghdl"),
    File_pattern(git_repo_path  / "units" / "unitTop" / "tb" / "AnyFileIDontWant.vhd),
    File_pattern(git_repo_path  / "units" / "unitTop" / "tb" / "VerificationDefinitions-p.vhd", when_simulator_is="modelsim") 
]
vunit_helpers.advanced_add_source_files(VU,lib,include_patterns,exclude_patterns)
```

## UVVM with GHDL
To run UVVM with GHDL, some additional compile and sim flags must be set. 
``` Python
VU = VUnit.from_argv()
vunit_helpers.set_ghdl_flags_for_UVVM(VU)
```

## TOML File for RustHDL
RustHDL is a free and open source VHDL language server. It's setup requires a TOML file, that lists all libraries and source files of a project. The fuction generate_rust_hdl_toml() will generate the TOML file for RustHDL based on all files that are included in the VUnit project. 
Call this function after adding the files to VUnit. 

``` Python
VU = VUnit.from_argv()
vunit_helpers.add_uvvm_sources(VU, "path/to/UVVM")

vunit_helpers.generate_rust_hdl_toml(VU, str(git_repo_path / "vhdl_ls.toml"), str(git_repo_path))
```



