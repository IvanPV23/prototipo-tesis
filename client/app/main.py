"""CLI mínima del nodo de campo."""
import argparse
import json

from .services.vale_service import ValeService
from .storage.local_db import LocalDB
from .sync.sync_engine import SyncEngine


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--device", required=True)
    parser.add_argument("--server", default="http://127.0.0.1:8000")
    sub = parser.add_subparsers(dest="action", required=True)
    crear = sub.add_parser("registrar")
    crear.add_argument("--tipo", choices=["SALIDA", "INGRESO"], required=True)
    crear.add_argument("--material", required=True)
    crear.add_argument("--cantidad", required=True, type=float)
    crear.add_argument("--proyecto", default="GENERAL")
    anular = sub.add_parser("anular")
    anular.add_argument("--vale", required=True)
    sub.add_parser("sync")
    args = parser.parse_args()
    db = LocalDB(args.db, args.device)
    if args.action == "registrar":
        print(ValeService(db, args.device).registrar(args.tipo, args.material, args.cantidad, args.proyecto).aggregate_id)
    elif args.action == "anular":
        print(ValeService(db, args.device).anular(args.vale).event_id)
    else:
        print(json.dumps(SyncEngine(db, args.device, args.server).sync(), default=str, indent=2))


if __name__ == "__main__":
    main()
