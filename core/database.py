import os
import sqlite3
import sys

class DatabaseManager:
    def __init__(self, db_path="vault.db"):
        # Add a 10-second timeout to allow threads to wait in line rather than instantly crashing
        self.conn = sqlite3.connect(db_path, check_same_thread=False, timeout=10.0)
        
        # Activate Write-Ahead Logging
        self.conn.execute("PRAGMA journal_mode=WAL;")
        
        self.create_tables()
        
    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                path TEXT UNIQUE NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tags(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_path TEXT NOT NULL,
                tag TEXT NOT NULL,
                is_manual BOOLEAN DEFAULT 0,
                UNIQUE(image_path,tag)
            )           
        ''')
        try:
            cursor.execute("ALTER TABLE tags ADD COLUMN is_manual BOOLEAN DEFAULT 0")
        except sqlite3.OperationalError:
            pass 
                
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS smart_folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                query_string TEXT NOT NULL
            )
        ''')
        self.conn.commit()   
   
    def add_smart_folder(self, name, query_string):
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO smart_folders (name, query_string) VALUES (?, ?)", (name, query_string))
        self.conn.commit()

    def get_smart_folders(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT name, query_string FROM smart_folders")
        return cursor.fetchall()

    def delete_smart_folder(self, name):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM smart_folders WHERE name = ?", (name,))
        self.conn.commit()
    
    def add_tag(self, image_path, tag):
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO tags (image_path,tag) VALUES (?,?)", (image_path, tag))
        self.conn.commit()
    
    def get_tags_for_image(self, image_path):
        cursor = self.conn.cursor()
        cursor.execute("SELECT tag, is_manual FROM tags WHERE image_path = ? ORDER BY is_manual DESC", (image_path,))
        return [f"⭐ {row[0]}" if row[1] else row[0] for row in cursor.fetchall()]
    
    def add_folder(self, name, path):
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO folders (name, path) VALUES (?, ?)", (name, path))
        self.conn.commit()
    
    def get_folders(self):
        cursor = self.conn.cursor()    
        cursor.execute("SELECT name, path FROM folders")
        return cursor.fetchall()
    
    def delete_folder(self, path):
        cursor = self.conn.cursor()
        try:
            wild_forward = f"{path}/%"
            wild_back = f"{path}\\%"
            cursor.execute("DELETE FROM folders WHERE path = ? OR path LIKE ? OR path LIKE ?", (path, wild_forward, wild_back))
            cursor.execute("DELETE FROM tags WHERE image_path LIKE ? OR image_path LIKE ?", (wild_forward, wild_back))
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            print(f"Failed to delete folder from DB: {e}")
        
    def search_images_by_tag(self, folder_path, search_term):
        cursor = self.conn.cursor()
        query="""
            SELECT DISTINCT image_path
            FROM tags
            WHERE image_path LIKE ? AND tag LIKE ?
        """
        folder_wildcard = f"{folder_path}%"   
        search_wildcard=f"{search_term}%"
        cursor.execute(query, (folder_wildcard, search_wildcard))
        return [row[0] for row in cursor.fetchall()]
    
    def get_unique_tags(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT tag FROM tags")
        return [row[0] for row in cursor.fetchall()]
    
    def global_search_by_tag(self, search_query):
        cursor = self.conn.cursor()
        terms = search_query.strip().lower().split()
        include_terms = []
        exclude_terms = []
        
        for term in terms:
            if term.startswith('-') and len(term) > 1:
                exclude_terms.append(f"%{term[1:]}%")
            else:
                include_terms.append(f"%{term}%")
                
        query = "SELECT DISTINCT image_path FROM tags"
        conditions = []
        params = []
        
        if include_terms:
            for _ in include_terms:
                conditions.append("image_path IN (SELECT image_path FROM tags WHERE tag LIKE ?)")
            params.extend(include_terms)
            
        if exclude_terms:
            for _ in exclude_terms:
                conditions.append("image_path NOT IN (SELECT image_path FROM tags WHERE tag LIKE ?)")
            params.extend(exclude_terms)
            
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            
        cursor.execute(query, tuple(params))
        return [row[0] for row in cursor.fetchall()]
    
    def batch_add_tags(self, tag_data_list):
        cursor = self.conn.cursor()
        if not tag_data_list:
            return
        try:
            data = []
            for image_path, tags in tag_data_list:
                for tag in tags:
                    data.append((image_path, tag))
            cursor.executemany("INSERT OR IGNORE INTO tags (image_path,tag) VALUES (?,?)", data)        
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            print(f"Batch DB save failed: {e}")
    
    def rename_folder(self, old_path, new_path, new_name):
        cursor = self.conn.cursor()
        is_windows = sys.platform.startswith('win')
        try:
            import os
            cursor.execute("UPDATE folders SET name = ?, path = ? WHERE path = ?", (new_name, new_path, old_path))
            norm_old_base = os.path.normpath(old_path) + os.sep
            norm_new_base = os.path.normpath(new_path) + os.sep
            test_old_base = norm_old_base.lower() if is_windows else norm_old_base
            
            cursor.execute("SELECT id, path FROM folders")
            for row_id, f_path in cursor.fetchall():
                norm_f = os.path.normpath(f_path)
                test_f = norm_f.lower() if is_windows else norm_f
                if test_f.startswith(test_old_base):
                    tail = norm_f[len(norm_old_base):]
                    updated_path = norm_new_base + tail
                    cursor.execute("UPDATE folders SET path = ? WHERE id = ?", (updated_path, row_id))
                    
            cursor.execute("SELECT id, image_path FROM tags")
            for row_id, img_path in cursor.fetchall():
                norm_img = os.path.normpath(img_path)
                test_img = norm_img.lower() if is_windows else norm_img
                if test_img.startswith(test_old_base):
                    tail = norm_img[len(norm_old_base):]
                    updated_img = norm_new_base + tail
                    cursor.execute("UPDATE tags SET image_path = ? WHERE id = ?", (updated_img, row_id))
                    
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            print(f"Failed to rename folder safely in DB: {e}")

   
    def update_image_tags(self, image_path, new_tags_list, is_manual=True):
        cursor = self.conn.cursor()
        try:
            if is_manual:
                cursor.execute("DELETE FROM tags WHERE image_path = ? AND is_manual = 1", (image_path,))
            else:
                cursor.execute("DELETE FROM tags WHERE image_path = ?", (image_path,))
                
            for tag in new_tags_list:
                cursor.execute("INSERT OR IGNORE INTO tags (image_path, tag, is_manual) VALUES (?, ?, ?)", 
                             (image_path, tag, 1 if is_manual else 0))
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            print(f"Failed to update tags in DB: {e}")   
    
    def delete_image(self, image_path):
        cursor = self.conn.cursor()
        try:
            cursor.execute("DELETE FROM tags WHERE image_path = ?", (image_path,))
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            print(f"Failed to delete image tags from DB: {e}")