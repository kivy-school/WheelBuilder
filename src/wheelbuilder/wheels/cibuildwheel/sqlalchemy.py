from wheelbuilder.protocols import CiWheelBase


class SQLAlchemy(CiWheelBase):
    name = "sqlalchemy"

    def env(self):
        env = self.base_env()
        env["CIBW_TEST_SKIP"] = "*"
        return env
