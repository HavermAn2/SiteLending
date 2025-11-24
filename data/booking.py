import sqlite3
import requests
con1=sqlite3.connect("data/art-updates.db")
cur1=con1.cursor()
      # список кортежей

try:
        with sqlite3.connect("data/art-updates.db") as con:
            cur = con.cursor()
            cur.execute("select * FROM photos where title = ?", ("A"))
            con.commit()
            rows = cur.fetchall()
            dates = [row for row in rows]
            print(dates)
          
except sqlite3.Error as e:
        print(f"Error in DB: {e}")