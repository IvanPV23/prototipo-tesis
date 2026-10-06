from client.app.storage.local_db import LocalDB
from client.app.services.vale_service import ValeService
def test_local_write_needs_no_network(tmp_path):
    db=LocalDB(str(tmp_path / "offline.db"))
    event=ValeService(db,"field-a").guardar(None,"V-1","Cemento",5)
    assert db.get_vale(event.aggregate_id)[0].cantidad == 5
    assert len(db.pending()) == 1
