import sqlite3
import requests
con1=sqlite3.connect("data/art-updates.db")
cur1=con1.cursor()
      # список кортежей

def remove_message(title: str) -> bool:
    try:
        with sqlite3.connect("data/art-updates.db") as con:
            cur = con.cursor()
            cur.execute("delete FROM photos WHERE description = ?", (title,))
            con.commit()
            rows = cur.fetchall()
            dates = [row for row in rows]
            print(dates)
            return True
    except sqlite3.Error as e:
        print(f"Error in DB: {e}")
        return False
remove_message("andreuis_bot")