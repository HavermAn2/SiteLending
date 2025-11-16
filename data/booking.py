import sqlite3

con = sqlite3.connect("data/booking.db")
cur = con.cursor()

# cur.execute("INSERT INTO bookings (date) VALUES (?)",
#     ("2025-11-19",) 
# )
# cur.execute(
#     "UPDATE bookings SET date = ? WHERE id = ?",
#     ("2025-11-18", 2)
# )
# con.commit()
cur.execute("Select * from bookings")
rows = cur.fetchall()      # список кортежей

for row in rows:
    print(row)