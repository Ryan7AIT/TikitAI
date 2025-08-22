import bcrypt

hashes = [
    b"$2y$10$mCyhC/nrimHXcgTMR52kkOy2f3pCRy3cWChPY3uoGix50p5WRCZyO",
    b"$2y$10$ozsF7lPhwpAhGFgnU/ftkOcvgp57IeXfapVqNXIEVXDhtl7G4mU.6"
]

for hashed in hashes:
    for i in range(10000):
        password = str(i).zfill(4)
        if bcrypt.checkpw(password.encode(), hashed):
            print(f"Match found for {hashed.decode()}: {password}")
            break

