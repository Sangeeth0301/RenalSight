"""Create an admin account (admins cannot self-register).  Usage: python create_admin.py email password "Name" """
import sys

from app.core.db import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models import User

if len(sys.argv) < 3:
    sys.exit('usage: python create_admin.py email password "Name"')
Base.metadata.create_all(engine)
with SessionLocal() as db:
    u = User(email=sys.argv[1].lower(), password_hash=hash_password(sys.argv[2]), name=sys.argv[3] if len(sys.argv) > 3 else "Admin", role="admin")
    db.add(u)
    db.commit()
    print("admin created:", u.email)
