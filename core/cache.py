import sqlite3
import os
import hashlib
from PyQt6.QtGui import QImage
from PyQt6.QtCore import QByteArray, QBuffer, QIODevice

class CacheManager:
    def __init__(self, cache_file="thumbnails.cache"):
        self.cache_file = cache_file
        self.conn = sqlite3.connect(self.cache_file, check_same_thread=False, timeout=10.0)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.create_table()

    def create_table(self):
        cursor = self.conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS thumbs (
                image_hash TEXT PRIMARY KEY,
                image_data BLOB
            )
        ''')
        self.conn.commit()

    def _get_hash(self, path):
        return hashlib.md5(path.encode('utf-8')).hexdigest()

    def get_thumbnail(self, path):
        """Returns a QImage if cached, otherwise None"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT image_data FROM thumbs WHERE image_hash = ?", (self._get_hash(path),))
        row = cursor.fetchone()
        
        if row:
            #Rebuild the QImage directly from the raw bytes
            qimg = QImage.fromData(row[0])
            return qimg
        return None

    def save_thumbnail(self, path, qimage):
        #Compresses QImage to a JPG BLOB and saves it
        # Convert QImage to raw byte array
        byte_array = QByteArray()
        buffer = QBuffer(byte_array)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        qimage.save(buffer, "JPG", 80) #80% quality
        
        blob_data = byte_array.data()
        
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO thumbs (image_hash, image_data)
            VALUES (?, ?)
        ''', (self._get_hash(path), blob_data))
        self.conn.commit()

    def clear_cache(self):
        """Wipes the database and shrinks the file size"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM thumbs") #Delete all the data
        self.conn.commit() #Commit and close transaction
        cursor.execute("VACUUM") #vacuum and shrink the file
        self.conn.commit()
        print("Cache completely cleared.")