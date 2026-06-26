from wheelbuilder.platforminfo import SDK
from wheelbuilder.protocols import MaturinWheelBase
from wheelbuilder.wheels.library.libffi import Libffi
from wheelbuilder.wheels.library.openssl import Openssl


class Bcrypt(MaturinWheelBase):
    def dependencies_libraries(self):
        if self.platform.sdk != SDK.android:
            return []
        return [Openssl, Libffi]

    def patches(self):
        return []
