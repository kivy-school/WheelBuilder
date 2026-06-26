from wheelbuilder.platforminfo import SDK
from wheelbuilder.protocols import MaturinWheelBase


class Pydantic_core(MaturinWheelBase):
    def env(self):
        e = super().env()
        if self.platform.sdk != SDK.android:
            # pyo3 0.28.3 for iOS requires framework linking against
            # Python.framework/Python. Python-Apple-support xcframework
            # provides no libpython3.13.a — only the framework binary.
            # Using PYO3_CONFIG_FILE overrides all of pyo3's auto-detection
            # (takes priority over PYO3_CROSS=1 and from_interpreter()).
            # suppress_build_script_link_lines=true + extra_build_script_line
            # emits the correct cargo:rustc-link-lib=framework=Python flags.
            gen_config = (
                "python3 -c \""
                "import pathlib,sysconfig,sys;"
                "d=sysconfig.get_config_var('LIBDIR');"
                "ext=sysconfig.get_config_var('EXT_SUFFIX');"
                "prefix=str(pathlib.Path(d).parent);"
                "v='{}.{}'.format(*sys.version_info[:2]);"
                "cfg='implementation=CPython\\n"
                "version={v}\\n"
                "shared=true\\n"
                "abi3=false\\n"
                "ext_suffix={ext}\\n"
                "suppress_build_script_link_lines=true\\n"
                "extra_build_script_line=cargo:rustc-link-lib=framework=Python\\n"
                "extra_build_script_line=cargo:rustc-link-search=framework={prefix}\\n"
                "pointer_width=64\\n'.format(v=v,prefix=prefix,ext=ext);"
                "pathlib.Path('/tmp/pyo3_ios_config.txt').write_text(cfg)"
                "\""
            )
            existing = e.get("CIBW_BEFORE_BUILD", "")
            before = gen_config
            if existing:
                before = f"{before} && {existing}"
            e["CIBW_BEFORE_BUILD_IOS"] = before
            existing_ios_env = e.get("CIBW_ENVIRONMENT_IOS", "")
            e["CIBW_ENVIRONMENT_IOS"] = f"{existing_ios_env} PYO3_CONFIG_FILE=/tmp/pyo3_ios_config.txt".strip()
        return e
