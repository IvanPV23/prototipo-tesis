import argparse
from .storage.local_db import LocalDB
from .services.vale_service import ValeService
from .sync.sync_engine import SyncEngine
def main():
    p=argparse.ArgumentParser(); p.add_argument("--db", required=True); p.add_argument("--device", required=True); p.add_argument("--server", default="http://127.0.0.1:8000")
    sub=p.add_subparsers(dest="action",required=True); c=sub.add_parser("crear"); c.add_argument("--codigo",required=True); c.add_argument("--material",required=True); c.add_argument("--cantidad",required=True,type=float); c.add_argument("--id")
    sub.add_parser("sync"); a=p.parse_args(); db=LocalDB(a.db)
    if a.action=="crear": print(ValeService(db,a.device).guardar(a.id,a.codigo,a.material,a.cantidad).event_id)
    else: print(SyncEngine(db,a.device,a.server).sync())
if __name__ == "__main__": main()
