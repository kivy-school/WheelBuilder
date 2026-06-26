from wheelbuilder.platforminfo import SDK
from wheelbuilder.protocols import CiWheelBase


class Kiwisolver(CiWheelBase):
    def env(self):
        env = self.base_env()
        if self.platform.sdk == SDK.android:
            env["CIBW_ENVIRONMENT_ANDROID"] = 'LDFLAGS="$LDFLAGS -lc++_shared -shared"'
        return env
