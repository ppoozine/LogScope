import bcrypt


class PasswordService:
    def __init__(self) -> None:
        self._rounds = 12

    def hash(self, plain: str) -> str:
        salt = bcrypt.gensalt(rounds=self._rounds)
        hashed_bytes = bcrypt.hashpw(plain.encode(), salt)
        return hashed_bytes.decode()

    def verify(self, plain: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(plain.encode(), hashed.encode())
        except ValueError:
            return False
