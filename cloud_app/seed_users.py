"""
seed_users.py -- crea o actualiza el login de una sucursal.

Uso (por ejemplo, desde la pestaña "Shell" de Render, para no manejar
contraseñas en texto plano fuera del servidor):

    python seed_users.py ARE encargado.are "contraseña-segura"
"""
import sys

from werkzeug.security import generate_password_hash

import db


def main():
    if len(sys.argv) != 4:
        print("Uso: python seed_users.py <BRANCH_CODE> <username> <password>")
        sys.exit(1)

    branch_code, username, password = sys.argv[1].strip().upper(), sys.argv[2].strip(), sys.argv[3]
    if len(password) < 8:
        print("La contraseña debe tener al menos 8 caracteres.")
        sys.exit(1)

    db.init_db()
    db.upsert_branch_user(branch_code, username, generate_password_hash(password))
    print(f"OK: sucursal {branch_code} -> usuario '{username}' actualizado.")


if __name__ == "__main__":
    main()
