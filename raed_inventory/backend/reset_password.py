import sqlite3
import bcrypt

db = sqlite3.connect('raed_inventory_local.db')
new_hash = bcrypt.hashpw(b'Admin@2024', bcrypt.gensalt(12)).decode()
db.execute('UPDATE users SET hashed_password=? WHERE username=?', (new_hash, 'admin'))
db.commit()
db.close()
print('Done!')
print('Username: admin')
print('Password: Admin@2024')
