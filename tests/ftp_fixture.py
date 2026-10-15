"""Deliberately synthetic FTP values; never copies the personal history."""
def seed_ftp(store, pairs=None):
    pairs = pairs or [('2019-07-18',200),('2027-01-01',220)]
    with store._transaction(write=True):
        store.connection.executemany('INSERT INTO ftp_history VALUES (?,?)',pairs)
        store.connection.execute("UPDATE ftp_history_state SET initialization='ready',revision=revision+1 WHERE singleton=1")
