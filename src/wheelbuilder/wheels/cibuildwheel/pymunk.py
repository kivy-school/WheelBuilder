from wheelbuilder.platforminfo import SDK
from wheelbuilder.platforms import Android_arm64, Android_x86_64
from wheelbuilder.protocols import CiWheelBase


class Pymunk(CiWheelBase):
    def env(self):
        env = self.base_env()
        if self.platform.sdk == SDK.android:
            # pymunk's pyproject.toml includes pp310-*/pp311-* (PyPy) selectors
            # which cibuildwheel 3.x rejects for android (PyPy not available).
            # Override CIBW_BUILD to CPython-only so those selectors are ignored.
            env["CIBW_BUILD"] = "cp3*"
            env["CIBW_TEST_SKIP"] = "*"
            env["CIBW_ENVIRONMENT_ANDROID"] = " ".join(
                [
                    'LDFLAGS="$LDFLAGS -llog -lm"',
                    'PIP_EXTRA_INDEX_URL="https://pypi-index.psychowaspx.workers.dev/simple/"',
                ]
            )
        return env

    @classmethod
    def supported_platforms(cls):
        return [Android_arm64(), Android_x86_64()]
