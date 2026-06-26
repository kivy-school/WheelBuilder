from wheelbuilder.platforminfo import SDK
from wheelbuilder.protocols import CiWheelBase
from wheelbuilder.wheels.library.libffi import Libffi


class Pycryptodome(CiWheelBase):
    def dependencies_libraries(self):
        if self.platform.sdk != SDK.android:
            return []
        return [Libffi]
